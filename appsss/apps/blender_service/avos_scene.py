"""
AVOS Blender scene builder. Runs INSIDE Blender (the `bpy` module, or
blender.exe -b --python server.py) - no other dependencies.

    build_and_render(scene: dict, out_path: str, assets_dir: str) -> dict

`scene` (produced by agentic_core.pipelines.blender.planner):

    {
      "environment": "grid_studio" | "desert" | "space" | "night_city_floor",
      "duration": 4.5, "fps": 24, "width": 540, "height": 960,
      "engine": "cycles" | "eevee" | "workbench", "samples": 16, "seed": 7,
      "actors": [{"id": "a1", "asset": "mannequin" | "<characters/*.fbx stem>",
                  "variant": "man" | "woman" | "giant" | "kid" | "robot" | "astronaut",
                  "action": "idle" | "walk" | ... | "<animations/*.fbx stem>",
                  "position": [x, y], "facing": 0, "scale": 1.0, "color": "#c68642",
                  "move_to": [x, y] | null}],
      "props": [{"type": "box" | "sphere" | ... | "<props/* stem>", "position": [x, y, z],
                 "scale": 1.0, "color": "#ff0000", "material": "plastic" | "gold" | "metal" | "glass",
                 "motion": "none" | "spin" | "float" | "fall" | "bounce" | "shake"}],
      "camera": {"shot": "wide" | "medium" | "close", "move": "static" | "push_in" | "pull_out"
                 | "orbit" | "pan" | "low_angle" | "track", "target": "a1"}
    }

Coordinates: metres, +z up, the camera looks from -y toward +y, so an
actor with facing=0 faces the camera. Unknown names fall back safely
(mannequin / idle / box) - a render never fails on a bad plan.
"""

import math
import os
import random
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Vector

BUILTIN_ACTIONS = (
    "idle", "walk", "run", "punch", "push", "jump", "wave", "fall",
    "celebrate", "dance", "point", "shocked", "fight_idle",
)
BUILTIN_PROPS = (
    "box", "sphere", "ball", "gold_bar", "balloon", "wall", "pillar", "rock",
    "tree", "bullet", "coin", "car_block", "planet", "moon", "sun_orb",
)
ENVIRONMENTS = ("grid_studio", "desert", "space", "night_city_floor")
VARIANTS = ("man", "woman", "giant", "kid", "robot", "astronaut")
ASSET_EXTS = (".fbx", ".glb", ".gltf", ".obj")

SKIN = "#c68642"


# -- utils -------------------------------------------------------------------


def _hex(color: str | None, default: str = "#cccccc") -> tuple[float, float, float, float]:
    c = (color or default).lstrip("#")
    if len(c) != 6:
        c = default.lstrip("#")
    srgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb]
    return (lin[0], lin[1], lin[2], 1.0)


def _mat(name: str, color: str, *, metallic=0.0, roughness=0.5, emission=0.0, transmission=0.0,
         subsurface=0.0) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    rgba = _hex(color)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if transmission and "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if subsurface and "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = subsurface
        bsdf.inputs["Subsurface Radius"].default_value = (0.3, 0.12, 0.08)
    if emission:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    m.diffuse_color = rgba  # used by Workbench
    return m


MATERIAL_PRESETS = {
    "plastic": dict(roughness=0.35),
    "matte": dict(roughness=0.9),
    "gold": dict(metallic=1.0, roughness=0.18),
    "metal": dict(metallic=1.0, roughness=0.3),
    "glass": dict(roughness=0.02, transmission=1.0),
    "glow": dict(emission=4.0),
    "rubber": dict(roughness=0.7),
}


def _link(obj, coll=None):
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


def _smooth(obj, subdiv: int = 0):
    for p in obj.data.polygons:
        p.use_smooth = True
    if subdiv:
        mod = obj.modifiers.new("subd", "SUBSURF")
        mod.levels = subdiv
        mod.render_levels = subdiv


def _new_obj_from_op(op, **kw):
    op(**kw)
    return bpy.context.active_object


def _assign(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)


# -- scene / render settings -------------------------------------------------


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def setup_render(scene_spec: dict):
    s = bpy.context.scene
    fps = int(scene_spec.get("fps") or 24)
    frames = max(2, round(float(scene_spec.get("duration") or 4) * fps))
    s.render.fps = fps
    s.frame_start, s.frame_end = 1, frames
    s.render.resolution_x = int(scene_spec.get("width") or 540) // 2 * 2
    s.render.resolution_y = int(scene_spec.get("height") or 960) // 2 * 2
    s.render.resolution_percentage = 100
    engine = (scene_spec.get("engine") or "cycles").lower()
    if engine == "workbench":
        s.render.engine = "BLENDER_WORKBENCH"
        sh = s.display.shading
        sh.light = "STUDIO"
        sh.color_type = "MATERIAL"
        sh.show_shadows = True
        sh.show_cavity = True
    elif engine == "eevee":
        s.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in _engines() else "BLENDER_EEVEE_NEXT"
        try:
            s.eevee.taa_render_samples = int(scene_spec.get("samples") or 32)
            s.eevee.use_shadows = True
        except AttributeError:
            pass
    else:
        s.render.engine = "CYCLES"
        s.cycles.device = "GPU" if scene_spec.get("gpu") else "CPU"
        s.cycles.samples = int(scene_spec.get("samples") or 16)
        s.cycles.use_denoising = True
        s.cycles.max_bounces = 4
        s.cycles.seed = int(scene_spec.get("seed") or 0)
        if scene_spec.get("gpu"):
            _enable_gpu()
    s.view_settings.view_transform = "AgX" if "AgX" in _view_transforms() else "Filmic"
    s.view_settings.look = "None"
    s.render.film_transparent = False
    return frames


def _engines():
    return [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]


def _view_transforms():
    try:
        return [e.identifier for e in bpy.context.scene.view_settings.bl_rna.properties["view_transform"].enum_items]
    except Exception:  # noqa: BLE001
        return []


def _enable_gpu():
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    return
            except TypeError:
                continue
    except Exception:  # noqa: BLE001
        pass


def set_output(path: str):
    s = bpy.context.scene
    im = s.render.image_settings
    if hasattr(im, "media_type"):
        im.media_type = "VIDEO"
    im.file_format = "FFMPEG"
    s.render.ffmpeg.format = "MPEG4"
    s.render.ffmpeg.codec = "H264"
    s.render.ffmpeg.constant_rate_factor = "HIGH"
    s.render.ffmpeg.audio_codec = "NONE"
    s.render.filepath = path


# -- environments ----------------------------------------------------------------


def _world(color_top: str, color_bottom: str | None = None, strength: float = 1.0, stars: bool = False):
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nodes, links = nt.nodes, nt.links
    bg = nodes.get("Background")
    bg.inputs["Strength"].default_value = strength
    if stars:
        tex = nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = 900.0
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.72
        ramp.color_ramp.elements[0].color = _hex(color_top)
        ramp.color_ramp.elements[1].position = 0.74
        ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
        links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], bg.inputs["Color"])
    elif color_bottom:
        coord = nodes.new("ShaderNodeTexCoord")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.45
        ramp.color_ramp.elements[0].color = _hex(color_bottom)
        ramp.color_ramp.elements[1].position = 0.75
        ramp.color_ramp.elements[1].color = _hex(color_top)
        mapr = nodes.new("ShaderNodeMapRange")
        mapr.inputs["From Min"].default_value = -1
        mapr.inputs["From Max"].default_value = 1
        links.new(coord.outputs["Generated"], sep.inputs["Vector"])
        links.new(sep.outputs["Z"], mapr.inputs["Value"])
        links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = _hex(color_top)
    w.color = _hex(color_top)[:3]


def _grid_material(base: str, line: str, cell: float = 1.0, width: float = 0.03):
    """Tiles from object-space XY (+Z on the back wall), so the grid wraps
    the cyclorama continuously."""
    m = bpy.data.materials.new("grid")
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.55
    uv = nodes.new("ShaderNodeUVMap")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uv.outputs["UV"], sep.inputs["Vector"])

    def line_mask(component):
        div = nodes.new("ShaderNodeMath")
        div.operation = "DIVIDE"
        div.inputs[1].default_value = cell
        links.new(sep.outputs[component], div.inputs[0])
        frac = nodes.new("ShaderNodeMath")
        frac.operation = "FRACT"
        links.new(div.outputs[0], frac.inputs[0])
        dist = nodes.new("ShaderNodeMath")  # distance to nearest integer
        dist.operation = "PINGPONG"
        dist.inputs[1].default_value = 0.5
        links.new(frac.outputs[0], dist.inputs[0])
        lt = nodes.new("ShaderNodeMath")
        lt.operation = "LESS_THAN"
        lt.inputs[1].default_value = width / cell
        links.new(dist.outputs[0], lt.inputs[0])
        return lt

    mx = nodes.new("ShaderNodeMath")
    mx.operation = "MAXIMUM"
    links.new(line_mask("X").outputs[0], mx.inputs[0])
    links.new(line_mask("Y").outputs[0], mx.inputs[1])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = _hex(base)
    mix.inputs["B"].default_value = _hex(line)
    links.new(mx.outputs[0], mix.inputs["Factor"])
    links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    m.diffuse_color = _hex(base)
    return m


def _cyclorama(material, width=40.0, depth=24.0, height=18.0, radius=5.0, back_y=10.0):
    """Floor that curves up into a back wall (photo-studio 'cyc'), with
    UVs in metres along the surface so a grid texture stays square."""
    import bmesh

    profile = []  # (y, z, distance along surface)
    dist = 0.0
    prev = None
    steps = 16
    pts = [(y, 0.0) for y in [-depth + back_y + i * (depth - radius) / 8 for i in range(9)]]
    cy, cz = back_y - radius, radius
    for i in range(1, steps + 1):
        a = -math.pi / 2 + (math.pi / 2) * i / steps
        pts.append((cy + radius * math.cos(a), cz + radius * math.sin(a)))
    for i in range(1, 9):
        pts.append((back_y, radius + i * (height - radius) / 8))
    for p in pts:
        if prev is not None:
            dist += math.dist(p, prev)
        profile.append((p[0], p[1], dist))
        prev = p
    cols = 41
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    grid = []
    for (y, z, d) in profile:
        row = []
        for c in range(cols):
            x = -width / 2 + width * c / (cols - 1)
            row.append((bm.verts.new((x, y, z)), (x, d)))
        grid.append(row)
    for r in range(len(grid) - 1):
        for c in range(cols - 1):
            quad = [grid[r][c], grid[r][c + 1], grid[r + 1][c + 1], grid[r + 1][c]]
            f = bm.faces.new([q[0] for q in quad])
            for loop, q in zip(f.loops, quad):
                loop[uv_layer].uv = q[1]
    mesh = bpy.data.meshes.new("cyc")
    bm.to_mesh(mesh)
    bm.free()
    obj = _link(bpy.data.objects.new("cyclorama", mesh))
    _smooth(obj)
    _assign(obj, material)
    return obj


def _area_light(name, location, target, power, size, color="#ffffff"):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = power
    data.size = size
    data.color = _hex(color)[:3]
    obj = _link(bpy.data.objects.new(name, data))
    obj.location = location
    _aim(obj, Vector(target))
    return obj


def _sun(name, rotation_deg, strength, color="#ffffff", angle_deg=3.0):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = strength
    data.color = _hex(color)[:3]
    data.angle = math.radians(angle_deg)
    obj = _link(bpy.data.objects.new(name, data))
    obj.rotation_euler = Euler([math.radians(a) for a in rotation_deg])
    return obj


def _aim(obj, target: Vector):
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def build_environment(name: str, rng: random.Random):
    if name == "desert":
        _world("#5aa0e6", "#f3dcc0", strength=1.0)
        mesh = bpy.data.meshes.new("dunes")
        import bmesh

        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=120, y_segments=120, size=60)
        mesh_obj = _link(bpy.data.objects.new("dunes", mesh))
        bm.to_mesh(mesh)
        bm.free()
        mesh_obj.location.y = 20
        tex = bpy.data.textures.new("dune_noise", "CLOUDS")
        tex.noise_scale = 6.0
        disp = mesh_obj.modifiers.new("disp", "DISPLACE")
        disp.texture = tex
        disp.strength = 1.6
        disp.mid_level = 0.6
        _smooth(mesh_obj)
        _assign(mesh_obj, _mat("sand", "#e2b47a", roughness=0.95))
        _sun("sun", (50, 0, 30 + rng.uniform(-15, 15)), 4.5, "#fff1d6", 1.5)
        return
    if name == "space":
        _world("#02030a", strength=1.0, stars=True)
        floor = _new_obj_from_op(bpy.ops.mesh.primitive_plane_add, size=80, location=(0, 10, 0))
        tex = bpy.data.textures.new("moon_noise", "CLOUDS")
        tex.noise_scale = 1.2
        sub = floor.modifiers.new("sub", "SUBSURF")
        sub.subdivision_type = "SIMPLE"
        sub.levels = sub.render_levels = 6
        disp = floor.modifiers.new("disp", "DISPLACE")
        disp.texture = tex
        disp.strength = 0.5
        _smooth(floor)
        _assign(floor, _mat("regolith", "#8d8d8d", roughness=0.95))
        _sun("sun", (60, 0, -35), 5.0, "#ffffff", 0.5)
        earth = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=3.5, location=(-6, 45, 14),
                                 segments=48, ring_count=24)
        _smooth(earth)
        _assign(earth, _mat("earth", "#2f6fd6", roughness=0.6))
        return
    if name == "night_city_floor":
        _world("#0b1026", "#1b2140", strength=0.6)
        _cyclorama(_grid_material("#141a2e", "#3cc6ff", cell=1.0, width=0.025))
        _area_light("key", (-4, -6, 7), (0, 0, 1), 900, 5, "#b8d4ff")
        _area_light("rim", (5, 6, 5), (0, 0, 1.2), 700, 4, "#ff4fd8")
        return
    # grid_studio (default) - the light-blue tiled studio look
    _world("#cfe6f5", strength=0.75)
    _cyclorama(_grid_material("#7cc8ec", "#e9f7ff", cell=1.0, width=0.03))
    _area_light("key", (-4.5, -6.5, 7.5), (0, 0, 1), 1600, 6)
    _area_light("fill", (6, -5, 3.5), (0, 0, 1), 500, 6, "#eaf6ff")
    _area_light("top", (0, 2, 9), (0, 0, 0), 600, 8)


# -- the built-in mannequin (Mixamo bone names) -----------------------------------

P = "mixamorig:"
# name, head, tail, parent, roll-up axis ("front" for vertical bones, "up" for arms)
BONES = [
    ("Hips", (0, 0, 0.98), (0, 0, 1.08), None),
    ("Spine", (0, 0, 1.08), (0, 0, 1.22), "Hips"),
    ("Spine1", (0, 0, 1.22), (0, 0, 1.34), "Spine"),
    ("Spine2", (0, 0, 1.34), (0, 0, 1.46), "Spine1"),
    ("Neck", (0, 0, 1.48), (0, 0, 1.58), "Spine2"),
    ("Head", (0, 0, 1.58), (0, 0, 1.80), "Neck"),
    ("LeftShoulder", (0.04, 0, 1.44), (0.17, 0, 1.44), "Spine2"),
    ("LeftArm", (0.17, 0, 1.44), (0.45, 0, 1.44), "LeftShoulder"),
    ("LeftForeArm", (0.45, 0, 1.44), (0.70, 0, 1.44), "LeftArm"),
    ("LeftHand", (0.70, 0, 1.44), (0.80, 0, 1.44), "LeftForeArm"),
    ("RightShoulder", (-0.04, 0, 1.44), (-0.17, 0, 1.44), "Spine2"),
    ("RightArm", (-0.17, 0, 1.44), (-0.45, 0, 1.44), "RightShoulder"),
    ("RightForeArm", (-0.45, 0, 1.44), (-0.70, 0, 1.44), "RightArm"),
    ("RightHand", (-0.70, 0, 1.44), (-0.80, 0, 1.44), "RightForeArm"),
    ("LeftUpLeg", (0.10, 0, 0.96), (0.10, 0, 0.53), "Hips"),
    ("LeftLeg", (0.10, 0, 0.53), (0.10, 0, 0.09), "LeftUpLeg"),
    ("LeftFoot", (0.10, 0, 0.09), (0.10, -0.15, 0.03), "LeftLeg"),
    ("RightUpLeg", (-0.10, 0, 0.96), (-0.10, 0, 0.53), "Hips"),
    ("RightLeg", (-0.10, 0, 0.53), (-0.10, 0, 0.09), "RightUpLeg"),
    ("RightFoot", (-0.10, 0, 0.09), (-0.10, -0.15, 0.03), "RightLeg"),
]

# Body parts: (bone, kind, size(radius or xyz), offset along bone 0..1 or explicit centre, material key)
VARIANT_STYLE = {
    "man": dict(skin=SKIN, shorts="#1b1b1b", top=None, build=1.0),
    "woman": dict(skin="#e0ac69", shorts="#1b1b1b", top="#1b1b1b", build=0.85),
    "giant": dict(skin="#3a3a3a", shorts=None, top=None, build=1.55),
    "kid": dict(skin="#d9a066", shorts="#2a5bd7", top="#f2c84b", build=0.85),
    "robot": dict(skin="#9aa3ad", shorts=None, top=None, build=1.0, metal=True),
    "astronaut": dict(skin="#f2f2f2", shorts=None, top=None, build=1.15, suit=True),
}


def _cylinder_between(a: Vector, b: Vector, r1: float, r2: float, verts=24):
    """A tapered capsule from a to b (rounded ends, no subdivision needed)."""
    import bmesh

    axis = b - a
    length = max(axis.length, 1e-4)
    rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bm = bmesh.new()
    rings = []
    cap = 4
    # rows: bottom hemisphere, body, top hemisphere
    profile = []
    for i in range(cap, 0, -1):
        ang = math.pi / 2 * i / cap
        profile.append((r1 * math.cos(ang), -r1 * math.sin(ang) * 0.6))
    for i in range(0, 5):
        k = i / 4
        profile.append((r1 + (r2 - r1) * k, length * k))
    for i in range(1, cap + 1):
        ang = math.pi / 2 * i / cap
        profile.append((r2 * math.cos(ang), length + r2 * math.sin(ang) * 0.6))
    for (r, z) in profile:
        ring = []
        for v in range(verts):
            t = 2 * math.pi * v / verts
            ring.append(bm.verts.new((max(r, 1e-4) * math.cos(t), max(r, 1e-4) * math.sin(t), z)))
        rings.append(ring)
    for r in range(len(rings) - 1):
        for v in range(verts):
            bm.faces.new([rings[r][v], rings[r][(v + 1) % verts], rings[r + 1][(v + 1) % verts], rings[r + 1][v]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.transform(bm, matrix=Matrix.Translation(a) @ rot, verts=bm.verts)
    mesh = bpy.data.meshes.new("capsule")
    bm.to_mesh(mesh)
    bm.free()
    obj = _link(bpy.data.objects.new("capsule", mesh))
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    return obj


def build_mannequin(variant: str, color: str | None) -> bpy.types.Object:
    style = VARIANT_STYLE.get(variant, VARIANT_STYLE["man"])
    build = style["build"]
    skin_color = color or style["skin"]
    if style.get("metal"):
        skin = _mat(f"skin_{variant}", skin_color, metallic=0.9, roughness=0.3)
    elif style.get("suit"):
        skin = _mat(f"skin_{variant}", skin_color, roughness=0.6)
    else:
        skin = _mat(f"skin_{variant}", skin_color, roughness=0.45, subsurface=0.15)
    cloth = _mat("shorts", style["shorts"], roughness=0.8) if style.get("shorts") else None
    top = _mat("top", style["top"], roughness=0.8) if style.get("top") else None
    visor = _mat("visor", "#111622", metallic=1.0, roughness=0.05) if style.get("suit") else None

    arm_data = bpy.data.armatures.new("rig")
    rig = _link(bpy.data.objects.new("actor_rig", arm_data))
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail, parent in BONES:
        eb = arm_data.edit_bones.new(P + name)
        eb.head, eb.tail = head, tail
        vertical = abs(tail[0] - head[0]) < 1e-6 and abs(tail[1] - head[1]) < 1e-6
        eb.align_roll(Vector((0, -1, 0)) if vertical else Vector((0, 0, 1)))
        if parent:
            eb.parent = arm_data.edit_bones[P + parent]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")

    w = build  # girth multiplier
    parts = []

    def part(obj, bone, material):
        vg = obj.vertex_groups.new(name=P + bone)
        vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        _assign(obj, material)
        parts.append(obj)

    def limb(bone, r1, r2, material, joint=True):
        b = arm_data.bones[P + bone]
        a, c = b.head_local.copy(), b.tail_local.copy()
        part(_cylinder_between(a, c, r1 * w, r2 * w), bone, material)
        if joint:
            part(_new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=r1 * w * 1.02, location=a,
                                  segments=16, ring_count=10), bone, material)

    # torso
    part(_cylinder_between(Vector((0, 0, 0.95)), Vector((0, 0, 1.12)), 0.15 * w, 0.14 * w), "Hips", cloth or skin)
    part(_cylinder_between(Vector((0, 0, 1.08)), Vector((0, 0, 1.24)), 0.135 * w, 0.14 * w), "Spine", top or skin)
    part(_cylinder_between(Vector((0, 0, 1.22)), Vector((0, 0, 1.36)), 0.135 * w, 0.15 * w), "Spine1", top or skin)
    chest = _cylinder_between(Vector((0, 0, 1.34)), Vector((0, 0, 1.50)), 0.15 * w, 0.11 * w)
    chest.scale = (1.22, 0.78, 1.0)
    part(chest, "Spine2", top or skin)
    limb("Neck", 0.05, 0.05, skin)
    head = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.11, location=(0, -0.01, 1.70),
                            segments=24, ring_count=16)
    head.scale = (0.9, 1.0, 1.12)
    part(head, "Head", skin)
    if style.get("suit"):
        helmet = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.17, location=(0, -0.01, 1.70),
                                  segments=24, ring_count=16)
        part(helmet, "Head", skin)
        v = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.12, location=(0, -0.08, 1.71),
                             segments=24, ring_count=16)
        v.scale = (1.0, 0.6, 0.8)
        part(v, "Head", visor)
    for side in ("Left", "Right"):
        limb(f"{side}Shoulder", 0.06, 0.06, top or skin, joint=False)
        limb(f"{side}Arm", 0.058, 0.048, skin)
        limb(f"{side}ForeArm", 0.046, 0.038, skin)
        hb = arm_data.bones[P + f"{side}Hand"]
        hand = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.05 * w,
                                location=(hb.head_local + hb.tail_local) / 2, segments=16, ring_count=10)
        hand.scale = (1.3, 0.6, 0.9)
        part(hand, f"{side}Hand", skin)
        if cloth:  # shorts to mid-thigh, bare leg below
            b = arm_data.bones[P + f"{side}UpLeg"]
            mid = b.head_local.lerp(b.tail_local, 0.42)
            part(_cylinder_between(b.head_local, mid, 0.092 * w, 0.085 * w), f"{side}UpLeg", cloth)
            part(_cylinder_between(mid, b.tail_local, 0.075 * w, 0.062 * w), f"{side}UpLeg", skin)
        else:
            limb(f"{side}UpLeg", 0.085, 0.065, skin)
        limb(f"{side}Leg", 0.062, 0.045, skin)
        fb = arm_data.bones[P + f"{side}Foot"]
        foot = _cylinder_between(Vector((fb.head_local.x, 0.03, 0.045)), Vector((fb.head_local.x, -0.17, 0.035)),
                                 0.05 * w, 0.042 * w)
        part(foot, f"{side}Foot", skin)

    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.active_object
    body.name = "actor_body"
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    _smooth(body)
    body.parent = rig
    mod = body.modifiers.new("rig", "ARMATURE")
    mod.object = rig
    body.modifiers.move(len(body.modifiers) - 1, 0)  # deform before subdivision
    rig["avos_builtin"] = True
    rig["avos_height"] = 1.82
    if variant == "giant":
        rig.scale = (1.15, 1.15, 1.15)
        rig["avos_height"] = 1.82 * 1.15
    elif variant == "kid":
        rig.scale = (0.68, 0.68, 0.68)
        rig["avos_height"] = 1.82 * 0.68
    return rig


# -- built-in procedural actions -----------------------------------------------------
#
# Local axes (set by align_roll above):
#   arms:   X+ raises the arm up; Z swings it front/back (sign differs per side)
#   legs:   X+ swings the leg forward; knee bend = Leg X-
#   spine:  X+ leans forward; Z bends sideways; Y twists


def _deg(v):
    return math.radians(v)


def _pose_fn(action: str):
    s = math.sin

    def arms_down(p, l=-78, r=-78):
        p["LeftArm"] = (l, 0, 0)
        p["RightArm"] = (r, 0, 0)

    def idle(t):
        p = {}
        arms_down(p, -80 + 2 * s(t * 2), -80 + 2 * s(t * 2))
        p["LeftForeArm"] = (0, 0, -8)
        p["RightForeArm"] = (0, 0, 8)
        p["Spine1"] = (1.5 * s(t * 2), 0, 0)
        p["Head"] = (0, 4 * s(t * 0.7), 0)
        return p, (0, 0, 0)

    def locomotion(t, hz, swing, knee, lean, bob, arm):
        ph = 2 * math.pi * hz * t
        p = {}
        p["LeftUpLeg"] = (swing * s(ph), 0, 0)
        p["RightUpLeg"] = (-swing * s(ph), 0, 0)
        p["LeftLeg"] = (-knee * max(0, -s(ph - 0.6)) - 5, 0, 0)
        p["RightLeg"] = (-knee * max(0, s(ph - 0.6)) - 5, 0, 0)
        p["LeftFoot"] = (8 * s(ph + 1), 0, 0)
        p["RightFoot"] = (-8 * s(ph + 1), 0, 0)
        arms_down(p, -72, -72)
        p["LeftArm"] = (-72, 0, -arm * s(ph))  # left arm forward with right leg
        p["RightArm"] = (-72, 0, -arm * s(ph))
        p["LeftForeArm"] = (0, 0, -20 - arm * 0.5)
        p["RightForeArm"] = (0, 0, 20 + arm * 0.5)
        p["Spine"] = (lean, 0, 0)
        p["Spine1"] = (0, 4 * s(ph), 0)
        return p, (0, 0, bob * abs(s(ph)))

    def walk(t):
        return locomotion(t, 0.9, 24, 35, 3, 0.03, 20)

    def run(t):
        return locomotion(t, 1.5, 42, 80, 14, 0.07, 45)

    def guard(p):
        p["LeftArm"] = (-55, 0, -35)
        p["RightArm"] = (-55, 0, 35)
        p["LeftForeArm"] = (0, 0, -120)
        p["RightForeArm"] = (0, 0, 120)
        p["LeftUpLeg"] = (12, 0, 0)
        p["RightUpLeg"] = (-10, 0, 0)
        p["LeftLeg"] = (-14, 0, 0)
        p["RightLeg"] = (-14, 0, 0)
        p["Spine"] = (8, 0, 0)

    def fight_idle(t):
        p = {}
        guard(p)
        return p, (0, 0, -0.03 + 0.025 * abs(s(t * 6)))

    def punch(t):
        p = {}
        guard(p)
        cycle = (t % 0.9) / 0.9
        side = "Right" if int(t / 0.9) % 2 == 0 else "Left"
        sign = 1 if side == "Right" else -1
        k = math.sin(math.pi * min(1.0, cycle / 0.45)) if cycle < 0.45 else 0.0
        p[f"{side}Arm"] = (-55 + 50 * k, 0, sign * (35 + 55 * k))
        p[f"{side}ForeArm"] = (0, 0, sign * (120 - 118 * k))
        p["Spine1"] = (0, sign * 22 * k, 0)
        return p, (0, 0, -0.03)

    def push(t):
        p = {}
        k = min(1.0, t / 0.6)
        p["LeftArm"] = (-10 * k - 60 * (1 - k), 0, -80 * k)
        p["RightArm"] = (-10 * k - 60 * (1 - k), 0, 80 * k)
        p["LeftForeArm"] = (0, 0, -15)
        p["RightForeArm"] = (0, 0, 15)
        p["Spine"] = (18 * k, 0, 0)
        p["LeftUpLeg"] = (25, 0, 0)
        p["RightUpLeg"] = (-20, 0, 0)
        p["LeftLeg"] = (-20, 0, 0)
        return p, (0, 0, -0.04)

    def jump(t):
        cycle = (t % 1.6) / 1.6
        p = {}
        if cycle < 0.25:  # crouch
            k = math.sin(math.pi / 2 * cycle / 0.25)
            z = -0.25 * k
            p["LeftUpLeg"] = p["RightUpLeg"] = (55 * k, 0, 0)
            p["LeftLeg"] = p["RightLeg"] = (-95 * k, 0, 0)
            p["Spine"] = (25 * k, 0, 0)
            arms_down(p, -80 + 10 * k, -80 + 10 * k)
            p["LeftArm"] = (-70, 0, 30 * k)
            p["RightArm"] = (-70, 0, -30 * k)
        elif cycle < 0.75:  # air
            k = (cycle - 0.25) / 0.5
            z = 0.9 * math.sin(math.pi * k)
            p["LeftUpLeg"] = p["RightUpLeg"] = (35 * math.sin(math.pi * k), 0, 0)
            p["LeftLeg"] = p["RightLeg"] = (-60 * math.sin(math.pi * k), 0, 0)
            p["LeftArm"] = p["RightArm"] = (60, 0, 0)
        else:  # land
            k = 1 - (cycle - 0.75) / 0.25
            z = -0.18 * k
            p["LeftUpLeg"] = p["RightUpLeg"] = (40 * k, 0, 0)
            p["LeftLeg"] = p["RightLeg"] = (-70 * k, 0, 0)
            arms_down(p, -40, -40)
        return p, (0, 0, z)

    def wave(t):
        p = {}
        arms_down(p)
        p["RightArm"] = (25, 0, 20)
        p["RightForeArm"] = (70, 0, 25 * s(t * 9))
        p["Head"] = (0, 0, -6)
        return p, (0, 0, 0)

    def celebrate(t):
        p = {}
        k = abs(s(t * 5))
        p["LeftArm"] = (60 + 15 * k, 0, 0)
        p["RightArm"] = (60 + 15 * k, 0, 0)
        p["LeftForeArm"] = (0, 0, -15)
        p["RightForeArm"] = (0, 0, 15)
        p["Head"] = (-12, 0, 0)
        return p, (0, 0, 0.12 * k)

    def dance(t):
        p = {}
        ph = t * 5
        p["LeftArm"] = (-20 + 50 * s(ph), 0, -20)
        p["RightArm"] = (-20 - 50 * s(ph), 0, 20)
        p["LeftForeArm"] = (0, 0, -60)
        p["RightForeArm"] = (0, 0, 60)
        p["Spine"] = (0, 0, 10 * s(ph))
        p["Hips"] = (0, 15 * s(ph / 2), 0)
        p["LeftUpLeg"] = (15 * max(0, s(ph)), 0, 0)
        p["RightUpLeg"] = (15 * max(0, -s(ph)), 0, 0)
        p["LeftLeg"] = (-25 * max(0, s(ph)), 0, 0)
        p["RightLeg"] = (-25 * max(0, -s(ph)), 0, 0)
        return p, (0, 0, 0.05 * abs(s(ph)))

    def point(t):
        p = {}
        arms_down(p)
        p["RightArm"] = (10 + 3 * s(t * 3), 0, 75)
        p["RightForeArm"] = (0, 0, 5)
        p["Head"] = (0, -10, 0)
        p["Spine1"] = (1.5 * s(t * 2), 0, 0)
        return p, (0, 0, 0)

    def shocked(t):
        p = {}
        k = min(1.0, t / 0.35)
        p["LeftArm"] = (-80 + 120 * k, 0, -10)
        p["RightArm"] = (-80 + 120 * k, 0, 10)
        p["LeftForeArm"] = (0, 0, -90 * k)
        p["RightForeArm"] = (0, 0, 90 * k)
        p["Spine"] = (-12 * k, 0, 0)
        p["Head"] = (-10 * k, 0, 0)
        return p, (0, 0, 0.03 * s(t * 30) * k)

    def fall(t):
        p = {}
        k = min(1.0, t / 0.9)
        p["LeftArm"] = (-78 + 118 * k, 0, -40 * k)
        p["RightArm"] = (-78 + 118 * k, 0, 40 * k)
        p["LeftUpLeg"] = p["RightUpLeg"] = (30 * k, 0, 0)
        p["Head"] = (20 * k, 0, 0)
        return p, (0, 0, 0)

    return {
        "idle": idle, "walk": walk, "run": run, "punch": punch, "push": push, "jump": jump,
        "wave": wave, "fall": fall, "celebrate": celebrate, "dance": dance, "point": point,
        "shocked": shocked, "fight_idle": fight_idle,
    }.get(action, idle)


def animate_builtin(rig, action: str, frames: int, fps: int, root_speed: float = 1.0):
    fn = _pose_fn(action)
    pose_bones = rig.pose.bones
    for pb in pose_bones:
        pb.rotation_mode = "XYZ"
    step = 2 if frames > 60 else 1
    for f in list(range(1, frames + 1, step)) + [frames]:
        t = (f - 1) / fps
        pose, hip_off = fn(t)
        for pb in pose_bones:
            name = pb.name[len(P):]
            rx, ry, rz = pose.get(name, (0, 0, 0))
            pb.rotation_euler = (_deg(rx), _deg(ry), _deg(rz))
            pb.keyframe_insert("rotation_euler", frame=f)
        hips = pose_bones[P + "Hips"]
        # Hips local Y is world up, local Z is world forward (-y).
        hips.location = (hip_off[0], hip_off[2], hip_off[1])
        hips.keyframe_insert("location", frame=f)
    if action == "fall":  # tip the whole body over backwards
        base = rig.rotation_euler.copy()
        for f in range(1, frames + 1, step):
            k = min(1.0, ((f - 1) / fps) / 0.9)
            k = k * k
            rig.rotation_euler = (base.x - _deg(88) * k, base.y, base.z)
            rig.keyframe_insert("rotation_euler", frame=f)


# -- library assets (Mixamo etc.) ----------------------------------------------------


def _find_asset(folder: Path, name: str) -> Path | None:
    if not name or not folder.is_dir():
        return None
    want = name.lower().replace(" ", "_")
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in ASSET_EXTS and p.stem.lower().replace(" ", "_") == want:
            return p
    return None


def _import(path: Path) -> list:
    before = set(bpy.data.objects)
    ext = path.suffix.lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path), automatic_bone_orientation=False)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=str(path))
    return [o for o in bpy.data.objects if o not in before]


def _bounds(objs) -> tuple[Vector, Vector]:
    bpy.context.view_layer.update()
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        if o.type != "MESH":
            continue
        for corner in o.bound_box:
            w = o.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    if lo.x > hi.x:
        return Vector((0, 0, 0)), Vector((0, 0, 1))
    return lo, hi


def load_library_character(path: Path):
    objs = _import(path)
    rig = next((o for o in objs if o.type == "ARMATURE"), None)
    root = rig or next((o for o in objs if o.parent is None), objs[0])
    # Normalise to ~1.8 m standing on the floor (Mixamo FBX are in cm).
    lo, hi = _bounds(objs)
    height = max(hi.z - lo.z, 1e-3)
    if abs(height - 1.8) > 0.3:
        root.scale = root.scale * (1.8 / height)
    bpy.context.view_layer.update()
    lo, _ = _bounds(objs)
    root.location.z -= lo.z
    root["avos_height"] = 1.8
    return root, rig


def _action_fcurves(action):
    """(collection, fcurve) pairs for legacy and layered (4.4+/5.x) actions."""
    out = []
    try:
        out.extend((action.fcurves, fc) for fc in action.fcurves)
    except Exception:  # noqa: BLE001
        pass
    for layer in getattr(action, "layers", []) or []:
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []) or []:
                out.extend((bag.fcurves, fc) for fc in bag.fcurves)
    return out


def _rig_height(armature_data) -> float:
    return max((b.head_local.z for b in armature_data.bones), default=1.0) or 1.0


def apply_library_animation(rig, anim_path: Path, frames: int):
    """Mixamo animations downloaded 'Without Skin' share bone names with
    any Mixamo character, so the action transfers directly. Only bone
    channels are kept (object transforms baked into the file would move or
    rescale the character), and hip translation is rescaled to this rig's
    proportions so units (cm vs m) can't throw the character off-screen."""
    objs = _import(anim_path)
    src = next((o for o in objs if o.type == "ARMATURE" and o.animation_data and o.animation_data.action), None)
    if src is None:
        for o in objs:
            bpy.data.objects.remove(o, do_unlink=True)
        return False
    ratio = _rig_height(rig.data) / _rig_height(src.data)
    action = src.animation_data.action.copy()
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    for coll, fc in _action_fcurves(action):
        path = fc.data_path
        if not path.startswith("pose.bones"):
            coll.remove(fc)
            continue
        if path.endswith(".location") and abs(ratio - 1.0) > 0.02:
            for kp in fc.keyframe_points:
                kp.co.y *= ratio
                kp.handle_left.y *= ratio
                kp.handle_right.y *= ratio
    rig.animation_data_create()
    ad = rig.animation_data
    start, end = action.frame_range
    length = max(1.0, end - start)
    track = ad.nla_tracks.new()
    strip = track.strips.new(action.name, 1, action)
    strip.action_frame_start, strip.action_frame_end = start, end
    strip.repeat = max(1.0, frames / length)
    if hasattr(strip, "action_slot") and getattr(action, "slots", None):
        try:
            strip.action_slot = action.slots[0]
        except Exception:  # noqa: BLE001
            pass
    strip.extrapolation = "HOLD"
    return True


def library_names(assets_dir: str | None) -> dict[str, list[str]]:
    out = {"characters": [], "animations": [], "props": []}
    if not assets_dir:
        return out
    for key in out:
        folder = Path(assets_dir) / key
        if folder.is_dir():
            out[key] = sorted({p.stem.lower().replace(" ", "_") for p in folder.iterdir()
                               if p.suffix.lower() in ASSET_EXTS})
    return out


def catalog(assets_dir: str | None) -> dict:
    lib = library_names(assets_dir)
    return {
        "environments": list(ENVIRONMENTS),
        "builtin_characters": ["mannequin"],
        "variants": list(VARIANTS),
        "builtin_actions": list(BUILTIN_ACTIONS),
        "builtin_props": list(BUILTIN_PROPS),
        "library_characters": lib["characters"],
        "library_animations": lib["animations"],
        "library_props": lib["props"],
    }


# -- actors ----------------------------------------------------------------------------


def place_actor(spec: dict, frames: int, fps: int, assets: Path | None):
    asset = (spec.get("asset") or "mannequin").lower()
    action = (spec.get("action") or "idle").lower()
    lib_char = _find_asset(assets / "characters", asset) if assets else None
    lib_anim = _find_asset(assets / "animations", action) if assets else None
    if lib_char is not None and lib_anim is None and assets is not None:
        # A Mixamo character must never stand in a T-pose: use the closest
        # animation you do have (same-meaning name, then an idle, then any).
        lib_anim = (_find_asset(assets / "animations", _closest_builtin(action))
                    or next((_find_asset(assets / "animations", n) for n in
                             ("idle", "breathing_idle", "standing", "happy_idle", "fight_idle")
                             if _find_asset(assets / "animations", n)), None)
                    or next(iter(sorted(p for p in (assets / "animations").iterdir()
                                        if p.suffix.lower() in ASSET_EXTS)), None)
                    if (assets / "animations").is_dir() else None)

    if lib_char is not None:
        root, rig = load_library_character(lib_char)
        animated = rig is not None and lib_anim is not None and apply_library_animation(rig, lib_anim, frames)
        if not animated and rig is not None:
            # No matching Mixamo animation: hold the import's own animation
            # (if any) rather than a T-pose.
            pass
        builtin = False
    else:
        root = build_mannequin(spec.get("variant") or "man", spec.get("color"))
        rig = root
        builtin = True

    scale = float(spec.get("scale") or 1.0)
    root.scale = root.scale * scale
    x, y = (spec.get("position") or [0, 0])[:2]
    start = Vector((float(x), float(y), root.location.z))
    root.location = start
    facing = float(spec.get("facing") or 0)
    move_to = spec.get("move_to")
    if move_to:
        end = Vector((float(move_to[0]), float(move_to[1]), start.z))
        direction = end - start
        if direction.length > 0.01:
            facing = math.degrees(math.atan2(direction.x, -direction.y))
    root.rotation_euler = (0, 0, math.radians(facing))
    if builtin:
        animate_builtin(rig, action if action in BUILTIN_ACTIONS else _closest_builtin(action), frames, fps)
    if move_to:
        root.keyframe_insert("location", frame=1)
        root.location = end
        root.keyframe_insert("location", frame=frames)
        _linear(root)
    height = float(root.get("avos_height", 1.8)) * scale
    return root, height


def _closest_builtin(action: str) -> str:
    aliases = {
        "walking": "walk", "running": "run", "sprint": "run", "boxing": "punch", "hit": "punch",
        "kick": "punch", "fight": "punch", "attack": "punch", "jumping": "jump", "leap": "jump",
        "waving": "wave", "hello": "wave", "victory": "celebrate", "cheer": "celebrate",
        "falling": "fall", "dying": "fall", "knocked_out": "fall", "dancing": "dance",
        "pointing": "point", "scared": "shocked", "surprised": "shocked", "standing": "idle",
        "talking": "idle", "pushing": "push", "stance": "fight_idle", "guard": "fight_idle",
    }
    return aliases.get(action, "idle")


def _linear(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return
    curves = []
    if hasattr(ad.action, "fcurves"):
        try:
            curves = list(ad.action.fcurves)
        except Exception:  # noqa: BLE001
            curves = []
    if not curves and getattr(ad.action, "layers", None):
        for layer in ad.action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    curves.extend(bag.fcurves)
    for fc in curves:
        if fc.data_path == "location":
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"


# -- props ------------------------------------------------------------------------------


def place_prop(spec: dict, frames: int, fps: int, assets: Path | None, rng: random.Random):
    kind = (spec.get("type") or "box").lower()
    scale = float(spec.get("scale") or 1.0)
    pos = list(spec.get("position") or [0, 0, 0]) + [0, 0, 0]
    loc = Vector((float(pos[0]), float(pos[1]), float(pos[2])))
    preset = MATERIAL_PRESETS.get((spec.get("material") or "plastic").lower(), MATERIAL_PRESETS["plastic"])
    color = spec.get("color")
    lib = _find_asset(assets / "props", kind) if assets else None
    if lib is not None:
        objs = _import(lib)
        root = next((o for o in objs if o.parent is None), objs[0])
        lo, hi = _bounds(objs)
        size = max((hi - lo).length, 1e-3)
        root.scale = root.scale * (scale * 1.0 / size)
        bpy.context.view_layer.update()
        lo, _ = _bounds(objs)
        root.location = loc + Vector((0, 0, root.location.z - lo.z))
        obj = root
    else:
        obj = _builtin_prop(kind, scale, color, preset)
        obj.location = loc + Vector((0, 0, obj.get("avos_rest_z", 0.0)))
    _prop_motion(obj, (spec.get("motion") or "none").lower(), frames, fps, rng)
    return obj


def _builtin_prop(kind: str, scale: float, color: str | None, preset: dict):
    def mat(default):
        return _mat(f"prop_{kind}", color or default, **preset)

    if kind in ("sphere", "ball", "planet", "moon", "sun_orb"):
        defaults = {"sphere": "#d9d9d9", "ball": "#e53935", "planet": "#2f6fd6", "moon": "#bdbdbd",
                    "sun_orb": "#ffb300"}
        r = {"ball": 0.25, "planet": 1.5, "moon": 1.0, "sun_orb": 1.5}.get(kind, 0.5) * scale
        o = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=r, segments=48, ring_count=24)
        _smooth(o)
        m = mat(defaults[kind])
        if kind == "sun_orb":
            m = _mat("sun_orb", color or "#ffb300", emission=8.0)
        _assign(o, m)
        o["avos_rest_z"] = r
        return o
    if kind == "gold_bar":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_cube_add, size=1)
        o.scale = (0.32 * scale, 0.14 * scale, 0.09 * scale)
        bev = o.modifiers.new("bevel", "BEVEL")
        bev.width = 0.015
        bev.segments = 3
        _assign(o, _mat("gold", color or "#ffb000", metallic=1.0, roughness=0.25))
        o["avos_rest_z"] = 0.045 * scale
        return o
    if kind == "coin":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_cylinder_add, radius=0.12 * scale, depth=0.02 * scale,
                             vertices=48)
        o.rotation_euler = (math.radians(90), 0, 0)
        _assign(o, _mat("gold", color or "#ffcc33", metallic=1.0, roughness=0.15))
        o["avos_rest_z"] = 0.12 * scale
        return o
    if kind == "balloon":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.35 * scale, segments=32, ring_count=16)
        o.scale.z = 1.2
        _smooth(o)
        _assign(o, _mat("balloon", color or "#e53935", roughness=0.15))
        o["avos_rest_z"] = 1.6 * scale
        return o
    if kind == "bullet":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_cylinder_add, radius=0.03 * scale, depth=0.12 * scale,
                             vertices=24)
        o.rotation_euler = (0, math.radians(90), 0)
        _assign(o, _mat("brass", color or "#c9a34a", metallic=1.0, roughness=0.25))
        o["avos_rest_z"] = 1.4
        return o
    if kind == "wall":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_cube_add, size=1)
        o.scale = (4 * scale, 0.3 * scale, 2.5 * scale)
        _assign(o, mat("#b0b8c0"))
        o["avos_rest_z"] = 1.25 * scale
        return o
    if kind == "pillar":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_cylinder_add, radius=0.3 * scale, depth=3 * scale, vertices=32)
        _smooth(o)
        _assign(o, mat("#e0e0e0"))
        o["avos_rest_z"] = 1.5 * scale
        return o
    if kind == "rock":
        o = _new_obj_from_op(bpy.ops.mesh.primitive_ico_sphere_add, radius=0.5 * scale, subdivisions=3)
        tex = bpy.data.textures.new("rock", "CLOUDS")
        d = o.modifiers.new("d", "DISPLACE")
        d.texture = tex
        d.strength = 0.25 * scale
        _smooth(o)
        _assign(o, mat("#7a7068"))
        o["avos_rest_z"] = 0.35 * scale
        return o
    if kind == "tree":
        trunk = _new_obj_from_op(bpy.ops.mesh.primitive_cylinder_add, radius=0.12 * scale, depth=1.2 * scale,
                                 location=(0, 0, 0.6 * scale))
        _assign(trunk, _mat("bark", "#6d4c41", roughness=0.9))
        crown = _new_obj_from_op(bpy.ops.mesh.primitive_cone_add, radius1=0.8 * scale, depth=2.0 * scale,
                                 location=(0, 0, 2.0 * scale))
        _assign(crown, _mat("leaves", color or "#2e7d32", roughness=0.8))
        crown.parent = trunk
        crown.location = (0, 0, 1.4 * scale)
        trunk["avos_rest_z"] = 0.6 * scale
        return trunk
    if kind == "car_block":
        body = _new_obj_from_op(bpy.ops.mesh.primitive_cube_add, size=1)
        body.scale = (2.0 * scale, 0.9 * scale, 0.6 * scale)
        bev = body.modifiers.new("bevel", "BEVEL")
        bev.width = 0.08
        bev.segments = 3
        _assign(body, _mat("car", color or "#e53935", metallic=0.5, roughness=0.25))
        body["avos_rest_z"] = 0.55 * scale
        return body
    # box (default)
    o = _new_obj_from_op(bpy.ops.mesh.primitive_cube_add, size=0.8 * scale)
    bev = o.modifiers.new("bevel", "BEVEL")
    bev.width = 0.02
    bev.segments = 2
    _assign(o, mat("#ff9800"))
    o["avos_rest_z"] = 0.4 * scale
    return o


def _prop_motion(obj, motion: str, frames: int, fps: int, rng: random.Random):
    if motion in ("none", ""):
        return
    rest = obj.location.copy()
    step = 2 if frames > 60 else 1
    for f in list(range(1, frames + 1, step)) + [frames]:
        t = (f - 1) / fps
        if motion == "spin":
            obj.rotation_euler.z = t * math.radians(120)
            obj.keyframe_insert("rotation_euler", frame=f)
            continue
        if motion == "float":
            obj.location = rest + Vector((0, 0, 0.15 * math.sin(t * 2.2)))
        elif motion == "fall":
            h = 3.0
            g = 9.8
            fall_t = math.sqrt(2 * h / g)
            if t < fall_t:
                z = h - 0.5 * g * t * t
            else:  # two damped bounces
                tb = t - fall_t
                v = g * fall_t * 0.35
                period = 2 * v / g
                z = max(0.0, v * (tb % period) - 0.5 * g * (tb % period) ** 2) if tb < period * 2 else 0.0
            obj.location = rest + Vector((0, 0, z))
        elif motion == "bounce":
            period = 0.7
            ph = (t % period) / period
            obj.location = rest + Vector((0, 0, 0.6 * 4 * ph * (1 - ph)))
        elif motion == "shake":
            obj.location = rest + Vector((0.03 * math.sin(t * 60), 0, 0.02 * math.sin(t * 47)))
        elif motion == "fly":
            obj.location = rest + Vector((0, -6 * min(1.0, t / max(0.5, frames / fps)), 0))
        obj.keyframe_insert("location", frame=f)


# -- camera ------------------------------------------------------------------------------


def place_camera(spec: dict, subjects: list[tuple], frames: int, fps: int, aspect: float):
    """Frame all actors (or the target) from the front; then animate the
    requested move. `subjects` = [(object, height)]."""
    s = bpy.context.scene
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 35
    cam_data.sensor_fit = "VERTICAL"
    cam_data.sensor_height = 24
    cam = _link(bpy.data.objects.new("cam", cam_data))
    s.camera = cam

    target_id = spec.get("target")
    shot = spec.get("shot") or "wide"
    # Wide/medium frame everyone (a fight needs both fighters); only a
    # close-up isolates the target.
    if shot == "close":
        focus = [sh for sh in subjects if sh[0].get("avos_id") == target_id] or subjects[:1]
    else:
        focus = subjects
    if focus:
        pts = []
        for obj, h in focus:
            pts.append(obj.matrix_world.translation.copy())
        centre = sum(pts, Vector()) / len(pts)
        span = max((max(p.x for p in pts) - min(p.x for p in pts)), 0.6)
        height = max(h for _, h in focus)
    else:
        centre, span, height = Vector((0, 0, 0)), 1.0, 1.8

    vfov = 2 * math.atan((cam_data.sensor_height / 2) / cam_data.lens)
    hfov = 2 * math.atan(math.tan(vfov / 2) * aspect)
    fit_h = {"wide": 1.6, "medium": 1.05, "close": 0.45}.get(shot, 1.6) * height
    look_z = {"wide": 0.5, "medium": 0.62, "close": 0.9}.get(shot, 0.5) * height
    dist_v = (fit_h / 2) / math.tan(vfov / 2)
    margin = {"wide": 1.4, "medium": 0.9}.get(shot, 0.0)
    dist_w = ((span + margin) / 2) / math.tan(hfov / 2) if shot != "close" else 0
    dist = max(dist_v, dist_w, 1.2)

    move = spec.get("move") or "static"
    cam_h = look_z + (0.25 if move != "low_angle" else -look_z + 0.25)
    aim = _link(bpy.data.objects.new("cam_target", None))
    aim.location = Vector((centre.x, centre.y, look_z))
    con = cam.constraints.new("TRACK_TO")
    con.target = aim
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    def cam_at(angle_deg, d, z):
        a = math.radians(angle_deg)
        return Vector((centre.x + d * math.sin(a), centre.y - d * math.cos(a), z))

    start_angle = -12.0
    if move == "orbit":
        keys = [(1, cam_at(-28, dist, cam_h)), (frames, cam_at(28, dist, cam_h))]
    elif move == "push_in":
        keys = [(1, cam_at(start_angle, dist * 1.25, cam_h)), (frames, cam_at(start_angle, dist * 0.82, cam_h))]
    elif move == "pull_out":
        keys = [(1, cam_at(start_angle, dist * 0.8, cam_h)), (frames, cam_at(start_angle, dist * 1.25, cam_h))]
    elif move == "pan":
        keys = [(1, cam_at(start_angle, dist, cam_h) + Vector((-1.2, 0, 0))),
                (frames, cam_at(start_angle, dist, cam_h) + Vector((1.2, 0, 0)))]
    elif move == "low_angle":
        keys = [(1, cam_at(start_angle, dist * 0.85, 0.25)), (frames, cam_at(start_angle + 10, dist * 0.78, 0.3))]
        aim.location.z = look_z * 1.15
    else:  # static / track: a gentle drift so it never looks frozen
        keys = [(1, cam_at(start_angle, dist, cam_h)), (frames, cam_at(start_angle + 4, dist * 0.96, cam_h))]
    for f, loc in keys:
        cam.location = loc
        cam.keyframe_insert("location", frame=f)
    if move == "track" and focus:
        obj = focus[0][0]
        for f in range(1, frames + 1, 4):
            s.frame_set(f)
            p = obj.matrix_world.translation
            aim.location = Vector((p.x, p.y, look_z))
            aim.keyframe_insert("location", frame=f)
            cam.location = cam_at(start_angle, dist, cam_h) + Vector((p.x - centre.x, p.y - centre.y, 0))
            cam.keyframe_insert("location", frame=f)
        s.frame_set(1)
    return cam


# -- entry point ------------------------------------------------------------------------


def build_scene(scene_spec: dict, assets_dir: str | None = None) -> dict:
    reset()
    rng = random.Random(int(scene_spec.get("seed") or 0))
    frames = setup_render(scene_spec)
    fps = bpy.context.scene.render.fps
    assets = Path(assets_dir) if assets_dir and Path(assets_dir).is_dir() else None
    env = scene_spec.get("environment") if scene_spec.get("environment") in ENVIRONMENTS else "grid_studio"
    build_environment(env, rng)

    subjects = []
    for i, actor in enumerate((scene_spec.get("actors") or [])[:6]):
        obj, height = place_actor(actor, frames, fps, assets)
        obj["avos_id"] = actor.get("id") or f"a{i + 1}"
        subjects.append((obj, height))
    for prop in (scene_spec.get("props") or [])[:12]:
        place_prop(prop, frames, fps, assets, rng)
    if not subjects:  # always have something to look at
        obj, height = place_actor({"asset": "mannequin", "action": "idle"}, frames, fps, assets)
        subjects.append((obj, height))

    s = bpy.context.scene
    s.frame_set(1)
    bpy.context.view_layer.update()
    aspect = s.render.resolution_x / s.render.resolution_y
    place_camera(scene_spec.get("camera") or {}, subjects, frames, fps, aspect)
    return {"frames": frames, "fps": fps, "environment": env, "actors": len(subjects)}


def build_and_render(scene_spec: dict, out_path: str, assets_dir: str | None = None) -> dict:
    info = build_scene(scene_spec, assets_dir)
    set_output(out_path)
    bpy.ops.render.render(animation=True)
    produced = out_path
    if not os.path.exists(produced):
        # Some Blender builds append the frame range to the file name.
        folder = Path(out_path).parent
        stem = Path(out_path).stem
        cands = sorted(folder.glob(f"{stem}*.mp4"))
        if cands:
            os.replace(cands[-1], out_path)
    info["path"] = out_path
    return info
