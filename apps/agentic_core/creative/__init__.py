"""AVOS creative core: one source of truth for every shot, shared by Facts and Animations.

    dna.py        Design DNA (the look and motion system of a series / style)
    scene.py      scene graph (who and what is where, the camera, the light) + motion blueprint (what moves when)
    compiler.py   scene + motion + DNA → the prompts each model gets (deterministic)
    skills.py     the SKILL.md files the agents read as their instructions

animation_studio/studio/creative/ is an identical copy (the studio container doesn't ship agentic_core); a test keeps
them the same.
"""
from . import compiler, dna, scene, skills  # noqa: F401
