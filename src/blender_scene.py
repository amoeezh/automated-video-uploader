"""Renders one procedural 3D comedic 'gag' clip as a PNG frame sequence.

Runs inside Blender's bundled Python interpreter via:
  blender --background --factory-startup --python blender_scene.py -- <args>
Deliberately avoids physics/drivers/parenting so it only depends on the
oldest, most stable parts of the bpy API (object keyframing, materials,
world/camera/light setup).
"""
import argparse
import math
import os
import random
import sys

import bpy

GAGS = ("bounce", "wobble", "spin_pop", "surprise_jump", "wiggle_dance")


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--gag", required=True, choices=GAGS)
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--width", type=int, default=540)
    p.add_argument("--height", type=int, default=960)
    p.add_argument("--fps", type=int, default=24)
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_material(name, color):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = 0.35
    return mat


def make_character(color):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0, 0, 1))
    body = bpy.context.active_object
    body.name = "Body"
    body.scale = (1.0, 0.9, 1.1)
    body.data.materials.append(make_material("BodyMat", color))

    eyes = []
    eye_mat = make_material("EyeMat", (0.02, 0.02, 0.02))
    for side in (-1, 1):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.16, location=(side * 0.4, -0.85, 1.5))
        eye = bpy.context.active_object
        eye.name = f"Eye_{side}"
        eye.data.materials.append(eye_mat)
        eyes.append(eye)

    return body, eyes


def setup_world(bg_color):
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (*bg_color, 1.0)
        bg.inputs[1].default_value = 1.0


def setup_camera_and_light():
    bpy.ops.object.camera_add(location=(0, -6.5, 1.6), rotation=(math.radians(83), 0, 0))
    bpy.context.scene.camera = bpy.context.active_object
    bpy.context.active_object.data.lens = 45

    bpy.ops.object.light_add(type="AREA", location=(2, -4, 4))
    bpy.context.active_object.data.energy = 800
    bpy.context.active_object.data.size = 4

    bpy.ops.object.light_add(type="AREA", location=(-3, -3, 2))
    bpy.context.active_object.data.energy = 300
    bpy.context.active_object.data.size = 3


def pose_for_frame(gag, f, fps, frame_end):
    """Returns (body_loc, body_scale, body_rot_z, eye_scale) for frame f."""
    t = f / fps

    if gag == "bounce":
        amplitude = 1.1
        phase = (t * 6.0) % (2 * math.pi)
        y = amplitude * abs(math.sin(phase))
        squash = max(0.0, 1.0 - y / amplitude)
        return (0, 0, 1 + y), (1.0 + 0.35 * squash, 0.9 + 0.35 * squash, 1.1 * (1.0 - 0.35 * squash)), 0.0, 1.0

    if gag == "wobble":
        angle = math.sin(t * 5.0) * math.radians(18)
        return (0, 0, 1), (1.0, 0.9, 1.1), angle, 1.0

    if gag == "spin_pop":
        spin_end = frame_end * 0.6
        if f <= spin_end:
            return (0, 0, 1), (1.0, 0.9, 1.1), t * 14.0, 1.0
        pop_t = (f - spin_end) / max(1, (frame_end - spin_end))
        s = 1.0 + pop_t * 0.8
        return (0, 0, 1), (s, s * 0.9, s * 1.1), (spin_end / fps) * 14.0, 1.0

    if gag == "surprise_jump":
        jump_frame = frame_end * 0.45
        if f < jump_frame:
            return (0, 0, 1), (1.0, 0.9, 1.1), 0.0, 1.0
        jt = min((f - jump_frame) / max(1, (frame_end - jump_frame)), 1.0)
        height = math.sin(jt * math.pi) * 2.2
        stretch = 1.0 + math.sin(jt * math.pi) * 0.3
        return (0, 0, 1 + height), (1.0 - stretch * 0.15, 0.9 - stretch * 0.15, 1.1 * stretch), 0.0, 1.4

    # wiggle_dance
    x = math.sin(t * 5.0) * 0.8
    angle = math.sin(t * 5.0 + 0.3) * math.radians(12)
    return (x, 0, 1), (1.0, 0.9, 1.1), angle, 1.0


def animate(body, eyes, gag, frame_end, fps):
    eye_base = [(-0.4, -0.85, 0.5), (0.4, -0.85, 0.5)]
    for f in range(0, frame_end + 1):
        bpy.context.scene.frame_set(f)
        loc, scale, rot_z, eye_scale = pose_for_frame(gag, f, fps, frame_end)

        body.location = loc
        body.scale = scale
        body.rotation_euler = (0, 0, rot_z)
        body.keyframe_insert(data_path="location", frame=f)
        body.keyframe_insert(data_path="scale", frame=f)
        body.keyframe_insert(data_path="rotation_euler", frame=f)

        for eye, (ox, oy, oz) in zip(eyes, eye_base):
            eye.location = (ox + loc[0], oy, oz + loc[2])
            eye.scale = (eye_scale, eye_scale, eye_scale)
            eye.keyframe_insert(data_path="location", frame=f)
            eye.keyframe_insert(data_path="scale", frame=f)


def main():
    args = parse_args()
    random.seed(args.seed)
    clear_scene()

    color = (random.uniform(0.5, 1.0), random.uniform(0.2, 0.9), random.uniform(0.3, 1.0))
    bg_color = (random.uniform(0.05, 0.5), random.uniform(0.05, 0.5), random.uniform(0.05, 0.5))

    body, eyes = make_character(color)
    setup_world(bg_color)
    setup_camera_and_light()

    scene = bpy.context.scene
    scene.render.fps = args.fps
    scene.render.resolution_x = args.width
    scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"

    try:
        scene.eevee.taa_render_samples = 16
    except AttributeError:
        pass

    frame_end = max(1, int(args.duration * args.fps))
    scene.frame_start = 0
    scene.frame_end = frame_end

    animate(body, eyes, args.gag, frame_end, args.fps)

    os.makedirs(args.out_dir, exist_ok=True)
    scene.render.filepath = os.path.join(args.out_dir, "frame_")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    main()
