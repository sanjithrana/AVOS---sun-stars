"""Run with Blender's Python (needs `bpy`):
    docker compose exec blender python -m pytest /app/blender_service/tests -q
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

bpy = pytest.importorskip("bpy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import avos_scene as A  # noqa: E402


def _scene(**kw):
    spec = {"duration": 0.5, "fps": 8, "width": 90, "height": 160, "engine": "workbench"}
    spec.update(kw)
    return spec


@pytest.mark.parametrize("env", A.ENVIRONMENTS)
def test_every_environment_builds(env):
    info = A.build_scene(_scene(environment=env, actors=[{"variant": "man"}]))
    assert info["environment"] == env and bpy.context.scene.camera is not None


@pytest.mark.parametrize("action", A.BUILTIN_ACTIONS)
def test_every_builtin_action_animates(action):
    A.build_scene(_scene(duration=1.0, actors=[{"id": "a1", "action": action}]))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    s = bpy.context.scene
    poses = []
    for f in range(1, s.frame_end + 1):
        s.frame_set(f)
        poses.append([tuple(round(v, 4) for v in pb.matrix.translation) for pb in rig.pose.bones])
    assert any(p != poses[0] for p in poses[1:])  # the body actually moves


@pytest.mark.parametrize("variant", A.VARIANTS)
def test_every_variant_and_unknown_names_fall_back(variant):
    info = A.build_scene(_scene(environment="nowhere", actors=[{"variant": variant, "action": "teleport"}],
                                props=[{"type": t} for t in A.BUILTIN_PROPS] + [{"type": "spaceship"}]))
    assert info["environment"] == "grid_studio" and info["actors"] == 1


def test_walker_moves_and_faces_its_direction():
    A.build_scene(_scene(duration=1.0, actors=[{"action": "walk", "position": [-1, 0], "move_to": [1, 0]}]))
    rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    s = bpy.context.scene
    s.frame_set(1)
    x0 = rig.matrix_world.translation.x
    s.frame_set(s.frame_end)
    assert rig.matrix_world.translation.x - x0 > 1.5
    assert abs(rig.rotation_euler.z - 1.5708) < 0.05  # facing screen-right


def test_library_character_and_animation(tmp_path):
    """A Mixamo-style pair (bones 'mixamorig:*', animation in cm) loads,
    animates, keeps its own scale and stays on screen."""
    (tmp_path / "characters").mkdir()
    (tmp_path / "animations").mkdir()
    A.reset()
    A.setup_render({"fps": 24, "duration": 1})
    rig = A.build_mannequin("woman", None)
    rig.name = "Armature"
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(filepath=str(tmp_path / "characters" / "lady.fbx"), use_selection=True,
                             bake_anim=False, add_leaf_bones=False)
    A.reset()
    A.setup_render({"fps": 24, "duration": 1})
    rig = A.build_mannequin("man", None)
    rig.name = "Armature"
    A.animate_builtin(rig, "jump", 24, 24)
    for o in list(bpy.data.objects):
        if o.type != "ARMATURE":
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.fbx(filepath=str(tmp_path / "animations" / "big_jump.fbx"), use_selection=True,
                             bake_anim=True, add_leaf_bones=False, global_scale=100.0)

    cat = A.catalog(str(tmp_path))
    assert cat["library_characters"] == ["lady"] and cat["library_animations"] == ["big_jump"]
    A.build_scene(_scene(duration=1.0, actors=[{"asset": "lady", "action": "big_jump"}]), str(tmp_path))
    lady = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    assert abs(lady.scale.x - 1.0) < 0.01
    s = bpy.context.scene
    heights = []
    for f in range(1, s.frame_end + 1):
        s.frame_set(f)
        heights.append(lady.pose.bones["mixamorig:Hips"].matrix.translation.z)
    assert 0.5 < min(heights) and max(heights) < 2.5 and max(heights) - min(heights) > 0.2


def test_render_writes_mp4(tmp_path):
    out = tmp_path / "shot.mp4"
    info = A.build_and_render(_scene(duration=0.5, actors=[{"action": "wave"}]), str(out))
    assert out.stat().st_size > 1000 and info["frames"] == 4
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0",
                            str(out)], capture_output=True, text=True)
    if probe.returncode == 0:
        assert probe.stdout.strip() == "h264"


def test_library_character_without_that_animation_never_t_poses(tmp_path):
    test_library_character_and_animation(tmp_path)  # builds lady.fbx + big_jump.fbx
    A.build_scene(_scene(duration=1.0, actors=[{"asset": "lady", "action": "backflip"}]), str(tmp_path))
    lady = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    assert lady.animation_data and lady.animation_data.nla_tracks  # fell back to big_jump
