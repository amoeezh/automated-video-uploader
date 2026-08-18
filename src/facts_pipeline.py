import json
import sys
import traceback
from datetime import date

import config
import facts_script_writer
import facts_script_reviewer
import facts_video_builder
import uploader


def log(msg):
    print(f"[{date.today().isoformat()}] {msg}", flush=True)


def update_history(title):
    with open(config.FACTS_STATE_FILE) as f:
        history = json.load(f)
    history["used_titles"].append(title)
    history["used_titles"] = history["used_titles"][-100:]
    with open(config.FACTS_STATE_FILE, "w") as f:
        json.dump(history, f, indent=2)


def run():
    log("Writing draft facts script (Gemini)...")
    draft = facts_script_writer.write_script()
    log(f"Draft title: {draft['title']} (format: {draft['format']})")

    log("Reviewing script (Groq/Llama)...")
    final_script = facts_script_reviewer.review_script(draft)

    log("Building video (TTS + charts + captions)...")
    video_path = facts_video_builder.build_video(final_script)
    log(f"Video rendered at {video_path}")

    log("Publishing video file to a public URL (GitHub release)...")
    video_url = uploader.publish_video_publicly(video_path)
    log(f"Public video URL: {video_url}")

    log("Uploading to Instagram...")
    media_id = uploader.upload_to_instagram(
        video_url, final_script["caption"], final_script.get("hashtags", [])
    )
    log(f"Published to Instagram, media id: {media_id}")

    if uploader.youtube_configured():
        log("Uploading to YouTube...")
        try:
            youtube_id = uploader.upload_to_youtube(
                video_path, final_script["title"], final_script["caption"], final_script.get("hashtags", [])
            )
            log(f"Published to YouTube, video id: {youtube_id}")
        except Exception as exc:
            log(f"YouTube upload failed (non-fatal): {exc}")
    else:
        log("YouTube not configured, skipping.")

    update_history(final_script["title"])
    log("Done.")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        log("PIPELINE FAILED")
        traceback.print_exc()
        sys.exit(1)
