import asyncio
import os
import textwrap
import uuid

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    ImageSequenceClip,
    concatenate_videoclips,
)

import animation_builder
import config
from retry import with_retry

VOICE = "hi-IN-MadhurNeural"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari[wdth,wght].ttf",
    "/System/Library/Fonts/Kohinoor.ttc",
    "/System/Library/Fonts/Supplemental/DevanagariMT.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _prosody_for_position(index, total):
    """Vary pacing so the narration doesn't sound flat: a slightly livelier
    setup, steady pace in the middle, and a punchy, emphasized delivery for
    the punchline/tag lines at the end."""
    if index == 0:
        return {"rate": "+3%", "pitch": "+1Hz"}
    if index >= total - 2:
        return {"rate": "+6%", "pitch": "+3Hz"}
    return {"rate": "-2%", "pitch": "+0Hz"}


async def _synthesize(text, out_path, rate="+0%", pitch="+0Hz"):
    communicate = edge_tts.Communicate(text, VOICE, rate=rate, pitch=pitch)
    await communicate.save(out_path)


def synthesize_line(text, out_path, rate="+0%", pitch="+0Hz"):
    with_retry(
        lambda: asyncio.run(_synthesize(text, out_path, rate=rate, pitch=pitch)),
        attempts=3, delay=10, label="edge-tts synthesis",
    )


def caption_image(text, width=config.VIDEO_WIDTH, height=config.VIDEO_HEIGHT):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(60)

    wrapped = textwrap.fill(text, width=18)
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


def build_gag_clip(gag, duration):
    frame_dir, fps = animation_builder.render_gag_clip(gag, duration, config.WORK_DIR)
    clip = ImageSequenceClip(frame_dir, fps=fps)
    clip = clip.set_duration(duration)
    clip = clip.resize(width=config.VIDEO_WIDTH)
    return clip


def build_video(script: dict) -> str:
    os.makedirs(config.WORK_DIR, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    sentence_clips = []
    total_sentences = len(script["sentences"])

    for i, (sentence, gag) in enumerate(zip(script["sentences"], script["visual_keywords"])):
        audio_path = os.path.join(config.WORK_DIR, f"{run_id}_{i}.mp3")
        prosody = _prosody_for_position(i, total_sentences)
        synthesize_line(sentence, audio_path, rate=prosody["rate"], pitch=prosody["pitch"])
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        bg_clip = build_gag_clip(gag, duration)

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
