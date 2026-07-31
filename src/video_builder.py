import asyncio
import os
import textwrap
import uuid

import edge_tts
import requests
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

import config

VOICE = "en-US-GuyNeural"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


async def _synthesize(text, out_path):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(out_path)


def synthesize_line(text, out_path):
    asyncio.run(_synthesize(text, out_path))


def caption_image(text, width=config.VIDEO_WIDTH, height=config.VIDEO_HEIGHT):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(64)

    wrapped = textwrap.fill(text, width=26)
    lines = wrapped.split("\n")

    line_height = font.getbbox("Ag")[3] + 20
    block_height = line_height * len(lines) + 80
    bar_top = height - block_height - 180
    draw.rectangle(
        [(0, bar_top), (width, bar_top + block_height)],
        fill=(0, 0, 0, 140),
    )

    y = bar_top + 40
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
        y += line_height

    return img


def search_pexels_video(keyword):
    resp = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": config.PEXELS_API_KEY},
        params={"query": keyword, "orientation": "portrait", "per_page": 5},
        timeout=30,
    )
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": keyword, "per_page": 5},
            timeout=30,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
    if not videos:
        return None

    video = videos[0]
    files = sorted(video["video_files"], key=lambda f: f.get("height", 0), reverse=True)
    best = next((f for f in files if f.get("height", 0) >= 720), files[0])
    return best["link"]


def download(url, out_path):
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1 << 16):
            f.write(chunk)


def fit_clip_to_frame(clip, duration):
    clip = clip.without_audio()
    if clip.duration < duration:
        clip = clip.fx(vfx.loop, duration=duration)
    else:
        clip = clip.subclip(0, duration)

    target_ratio = config.VIDEO_WIDTH / config.VIDEO_HEIGHT
    clip_ratio = clip.w / clip.h
    if clip_ratio > target_ratio:
        clip = clip.resize(height=config.VIDEO_HEIGHT)
        clip = clip.crop(x_center=clip.w / 2, width=config.VIDEO_WIDTH)
    else:
        clip = clip.resize(width=config.VIDEO_WIDTH)
        clip = clip.crop(y_center=clip.h / 2, height=config.VIDEO_HEIGHT)

    return clip


def build_video(script: dict) -> str:
    os.makedirs(config.WORK_DIR, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    sentence_clips = []

    for i, (sentence, keyword) in enumerate(zip(script["sentences"], script["visual_keywords"])):
        audio_path = os.path.join(config.WORK_DIR, f"{run_id}_{i}.mp3")
        synthesize_line(sentence, audio_path)
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        video_url = search_pexels_video(keyword) or search_pexels_video(script["title"])
        raw_path = os.path.join(config.WORK_DIR, f"{run_id}_{i}.mp4")
        download(video_url, raw_path)
        bg_clip = fit_clip_to_frame(VideoFileClip(raw_path), duration)

        cap_img = caption_image(sentence)
        cap_path = os.path.join(config.WORK_DIR, f"{run_id}_{i}.png")
        cap_img.save(cap_path)
        caption_clip = ImageClip(cap_path).set_duration(duration)

        composite = CompositeVideoClip([bg_clip, caption_clip]).set_audio(audio_clip)
        sentence_clips.append(composite)

    final = concatenate_videoclips(sentence_clips, method="compose")
    out_path = os.path.join(config.WORK_DIR, f"{run_id}_final.mp4")
    final.write_videofile(
        out_path,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="veryfast",
        logger=None,
    )
    return out_path
