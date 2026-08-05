import asyncio
import os
import textwrap
import uuid

import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

import chart_builder
import config
from retry import with_retry

VOICE = "en-US-AriaNeural"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
SENTENCE_GAP = 0.2


def _font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


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
    font = _font(56)

    wrapped = textwrap.fill(text, width=28)
    lines = wrapped.split("\n")

    line_height = font.getbbox("Ag")[3] + 18
    block_height = line_height * len(lines) + 70
    bar_top = height - block_height - 160
    draw.rectangle(
        [(0, bar_top), (width, bar_top + block_height)],
        fill=(0, 0, 0, 150),
    )

    y = bar_top + 35
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) / 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))
        y += line_height

    return img


def _prosody_for_position(index, total):
    if index == 0:
        return {"rate": "+2%", "pitch": "+1Hz"}
    if index >= total - 2:
        return {"rate": "+4%", "pitch": "+2Hz"}
    return {"rate": "-1%", "pitch": "+0Hz"}


def build_quick_facts_video(script: dict) -> str:
    os.makedirs(config.FACTS_WORK_DIR, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    sentence_clips = []
    facts = script["facts"]

    for i, fact in enumerate(facts):
        audio_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_{i}.mp3")
        prosody = _prosody_for_position(i, len(facts))
        synthesize_line(fact["sentence"], audio_path, rate=prosody["rate"], pitch=prosody["pitch"])
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        chart_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_{i}_chart.mp4")
        chart_builder.render_chart_clip(fact, duration, chart_path)
        bg_clip = VideoFileClip(chart_path).resize(width=config.VIDEO_WIDTH).set_duration(duration)

        cap_img = caption_image(fact["sentence"])
        cap_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_{i}.png")
        cap_img.save(cap_path)
        caption_clip = ImageClip(cap_path).set_duration(duration)

        composite = CompositeVideoClip([bg_clip, caption_clip]).set_audio(audio_clip)
        sentence_clips.append(composite)

    final = concatenate_videoclips(sentence_clips, method="compose")
    out_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_final.mp4")
    final.write_videofile(
        out_path, fps=30, codec="libx264", audio_codec="aac", threads=4,
        preset="veryfast", logger=None,
    )
    return out_path


def build_timeline_race_video(script: dict) -> str:
    os.makedirs(config.FACTS_WORK_DIR, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    sentences = script["sentences"]

    audio_clips = []
    caption_specs = []
    cursor = 0.0
    for i, sentence in enumerate(sentences):
        audio_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_{i}.mp3")
        prosody = _prosody_for_position(i, len(sentences))
        synthesize_line(sentence, audio_path, rate=prosody["rate"], pitch=prosody["pitch"])
        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration

        audio_clips.append(audio_clip.set_start(cursor))
        caption_specs.append((sentence, cursor, duration))
        cursor += duration + SENTENCE_GAP

    total_duration = max(1.0, cursor - SENTENCE_GAP)

    spec = chart_builder.validate_timeline_spec(script)
    chart_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_race.mp4")
    chart_builder.render_timeline_race_clip(spec, total_duration, chart_path)
    bg_clip = VideoFileClip(chart_path).resize(width=config.VIDEO_WIDTH).set_duration(total_duration)

    caption_clips = []
    for i, (sentence, start, duration) in enumerate(caption_specs):
        cap_img = caption_image(sentence)
        cap_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_cap_{i}.png")
        cap_img.save(cap_path)
        caption_clips.append(ImageClip(cap_path).set_duration(duration).set_start(start))

    final = CompositeVideoClip([bg_clip] + caption_clips).set_audio(CompositeAudioClip(audio_clips))
    final = final.set_duration(total_duration)

    out_path = os.path.join(config.FACTS_WORK_DIR, f"{run_id}_final.mp4")
    final.write_videofile(
        out_path, fps=30, codec="libx264", audio_codec="aac", threads=4,
        preset="veryfast", logger=None,
    )
    return out_path


def build_video(script: dict) -> str:
    if script.get("format") == "timeline_race":
        return build_timeline_race_video(script)
    return build_quick_facts_video(script)
