import os
import random
import shutil
import subprocess
import uuid

from retry import with_retry

BLENDER_SCENE_SCRIPT = os.path.join(os.path.dirname(__file__), "blender_scene.py")
RENDER_FPS = 24
RENDER_WIDTH = 540
RENDER_HEIGHT = 960


def _render(gag, duration, out_dir):
    cmd = [
        "blender",
        "--background",
        "--factory-startup",
        "--python", BLENDER_SCENE_SCRIPT,
        "--",
        "--gag", gag,
        "--duration", str(duration),
        "--out-dir", out_dir,
        "--width", str(RENDER_WIDTH),
        "--height", str(RENDER_HEIGHT),
        "--fps", str(RENDER_FPS),
        "--seed", str(random.randint(0, 1_000_000)),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(
            f"Blender render failed for gag={gag}: {result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    frames = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
    if not frames:
        raise RuntimeError(f"Blender produced no frames for gag={gag} in {out_dir}")


def render_gag_clip(gag, duration, work_dir):
    """Renders a procedural 3D gag animation and returns (frame_dir, fps)."""
    out_dir = os.path.join(work_dir, f"anim_{uuid.uuid4().hex[:8]}")
    os.makedirs(out_dir, exist_ok=True)

    def attempt():
        if os.path.isdir(out_dir):
            shutil.rmtree(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        _render(gag, duration, out_dir)

    with_retry(attempt, attempts=3, delay=10, label=f"Blender render ({gag})")
    return out_dir, RENDER_FPS
