"""Every skill must actually import, and every skill must reach the Skills tab.

A new skill with a single wrong import takes down `pipeline.py`, and with it the whole Skills tab -- not just itself.
That is how `asmr_cutting` shipped with `from . import config` (the rest of the codebase uses `from .. import config`,
inside the function) and nothing appeared in the tab at all. One import error, five skills gone.

These tests are deliberately dumb and fast. They are a tripwire, not a check of behaviour.
"""
from __future__ import annotations

import importlib
import pkgutil
import re
from pathlib import Path

import pytest

from studio.skilllab import pipeline

SKILL_IDS = {"mechanical-toy", "company-story", "asmr-cooking", "motion-graphics", "asmr-cutting"}


def test_every_module_in_skilllab_imports():
    import studio.skilllab as pkg
    for m in pkgutil.iter_modules(pkg.__path__):
        if m.ispkg:
            continue
        importlib.import_module(f"studio.skilllab.{m.name}")      # an ImportError here fails the whole tab


def test_every_skill_reaches_the_skills_tab():
    assert SKILL_IDS <= set(pipeline.SKILLS), f"missing from the tab: {SKILL_IDS - set(pipeline.SKILLS)}"
    for sid, mod in pipeline.SKILLS.items():
        spec = pipeline.spec_of({"skill": sid})
        assert spec["stages"], sid
        assert set(spec["run"]) == set(spec["stages"]), f"{sid}: a stage with no function to run it"
        assert all(st in spec["labels"] for st in spec["stages"]), f"{sid}: a stage with no label"
        for key in ("id", "name", "group", "input", "aspect", "aspects", "seconds", "default_seconds"):
            assert key in mod.INFO, f"{sid}: INFO has no {key!r}, so the create page cannot draw it"
        assert mod.INFO["default_seconds"] in mod.INFO["seconds"], f"{sid}: the default length is not one of the choices"
        assert mod.INFO["aspect"] in mod.INFO["aspects"], f"{sid}: the default shape is not one of the choices"


def test_no_module_imports_a_sibling_that_does_not_exist():
    """The exact mistake, caught statically: `from . import x` where skilllab/x.py is not there."""
    d = Path(__file__).resolve().parents[1] / "studio" / "skilllab"
    have = {p.stem for p in d.glob("*.py")} | {p.name for p in d.iterdir() if p.is_dir()}
    wrong = []
    for f in sorted(d.glob("*.py")):
        for i, line in enumerate(f.read_text("utf-8").splitlines(), 1):
            m = re.match(r"\s*from \. import \(?(.+?)\)?$", line)
            if not m:
                continue
            for name in (x.strip().split(" as ")[0].strip("()") for x in m.group(1).split(",")):
                if name and not name.endswith("\\") and name not in have:
                    wrong.append(f"{f.name}:{i} -> from . import {name}")
    assert not wrong, "these name a module that is not in skilllab/:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize("sid", sorted(SKILL_IDS))
def test_each_skill_can_describe_itself_without_a_run(sid):
    mod = pipeline.SKILLS[sid]
    assert mod.INFO["id"] == sid
    assert mod.INFO.get("examples"), f"{sid}: no examples, so the create page has no chips"
    for key, val in (("make", list), ("outputs", list)):
        assert isinstance(mod.INFO.get(key, []), val)
