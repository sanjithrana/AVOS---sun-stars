"""Actions → poses over time, with anticipation, follow-through and squash & stretch."""
from __future__ import annotations

import math

from .rig import Pose

ACTION_EXPR = {"idle": "happy", "wave": "happy", "walk": "happy", "run": "determined", "jump": "excited", "dance": "laugh",
               "cheer": "excited", "point": "determined", "think": "confused", "sit": "neutral", "cry": "cry", "laugh": "laugh",
               "shock": "surprised", "talk": "happy", "sleep": "sleepy", "hug": "love", "angry": "angry", "shy": "shy",
               "love": "love", "fall": "scream", "clap": "excited", "bow": "happy"}
ALIASES = {"stand": "idle", "standing": "idle", "smile": "idle", "look": "idle", "wait": "idle", "walking": "walk", "running": "run",
           "jumping": "jump", "dancing": "dance", "celebrate": "cheer", "yay": "cheer", "pointing": "point", "thinking": "think",
           "sitting": "sit", "crying": "cry", "laughing": "laugh", "surprised": "shock", "surprise": "shock", "scared": "shock",
           "talking": "talk", "speak": "talk", "say": "talk", "sleeping": "sleep", "hugging": "hug", "mad": "angry",
           "blush": "shy", "heart": "love", "trip": "fall", "falling": "fall", "clapping": "clap", "bowing": "bow",
           "跑": "run", "走": "walk", "跳": "jump", "揮手": "wave", "哭": "cry", "笑": "laugh", "想": "think", "坐": "sit",
           "睡": "sleep", "抱": "hug", "生氣": "angry", "害羞": "shy", "驚": "shock", "說": "talk", "跳舞": "dance", "歡呼": "cheer"}
MOVING = {"walk": 0.22, "run": 0.48}   # screen widths per second when an actor travels


def canon(action: str | None) -> str:
    a = str(action or "idle").strip().lower()
    from .rig import POSES
    if a in POSES:
        return a
    for k, v in ALIASES.items():
        if k in a:
            return v
    return "idle"


def ease(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def back(x: float, s: float = 1.6) -> float:
    x = max(0.0, min(1.0, x)) - 1
    return x * x * ((s + 1) * x + s) + 1


def pose_for(action: str, t: float, dur: float, bpm: float | None = None, seed: int = 0, intensity: float = 1.0) -> Pose:
    a = canon(action)
    ph = seed * 0.37
    beat = 60.0 / bpm if bpm and 60 <= bpm <= 200 else 0.5
    p = Pose()
    breathe = math.sin(t * 2.2 + ph)
    p.dy = -breathe * 0.4
    p.arm_l = (-10 - breathe, -5)
    p.arm_r = (10 + breathe, 5)
    p.blink = (t + ph * 3) % 3.3 < 0.12
    p.look = (0.15 * math.sin(t * 0.7 + ph), 0.0)
    k = intensity
    if a == "idle":
        p.head = 2 * math.sin(t * 1.3 + ph)
    elif a == "wave":
        w = math.sin(t * 9 + ph)
        p.arm_r = (150, 150 + 30 * w)
        p.head = 4
        p.lean = -2
    elif a in ("walk", "run"):
        sp = 7.0 if a == "walk" else 12.0
        s = math.sin(t * sp + ph)
        amp = (26 if a == "walk" else 42) * k
        p.turn = 0.55
        p.leg_l = (amp * s, amp * s - (18 if s < 0 else 4))
        p.leg_r = (-amp * s, -amp * s - (18 if s > 0 else 4))
        p.arm_l = (-amp * 0.9 * s, -amp * 0.9 * s + 25)
        p.arm_r = (amp * 0.9 * s, amp * 0.9 * s + 25)
        p.dy = -abs(math.cos(t * sp + ph)) * (2.0 if a == "walk" else 5.0)
        p.lean = 4 if a == "walk" else 13
        p.look = (0.6, 0)
    elif a == "jump":
        period = max(0.9, min(1.6, dur / 2 if dur > 1.8 else dur))
        x = (t % period) / period
        if x < 0.22:      # anticipation: crouch
            c = ease(x / 0.22)
            p.squash, p.dy = 0.16 * c, 0
            p.arm_l, p.arm_r = (-30 * c, -20), (30 * c, 20)
            p.leg_l, p.leg_r = (-18 * c, 22 * c), (18 * c, -22 * c)
        elif x < 0.78:    # flight with stretch
            f = (x - 0.22) / 0.56
            h = math.sin(f * math.pi)
            p.dy = -46 * h * k
            p.squash = -0.12 * (1 - abs(f - 0.3) * 2) if f < 0.6 else 0
            p.arm_l, p.arm_r = (-150 + 20 * f, -160), (150 - 20 * f, 160)
            p.leg_l, p.leg_r = (-12, 25), (12, -25)
        else:             # land + settle
            f = (x - 0.78) / 0.22
            p.squash = 0.14 * (1 - ease(f))
            p.arm_l, p.arm_r = (-40, -30), (40, 30)
    elif a == "dance":
        b = math.sin(t * math.pi * 2 / (beat * 2) + ph)
        p.lean = 9 * b
        p.head = -6 * b
        p.arm_l = (-120 - 30 * b, -150)
        p.arm_r = (60 + 50 * b, 120 + 30 * b)
        p.dy = -abs(math.sin(t * math.pi / beat)) * 4
        p.leg_l, p.leg_r = (-10 + 8 * b, -6), (10 + 8 * b, 6)
    elif a == "cheer" or a == "clap":
        b = math.sin(t * 10 + ph)
        if a == "cheer":
            p.arm_l, p.arm_r = (-155 + 10 * b, -170), (155 - 10 * b, 170)
            p.dy = -abs(math.sin(t * 5)) * 6
        else:
            gap = 10 + 10 * b
            p.arm_l, p.arm_r = (-50, 60 - gap), (50, -60 + gap)
            p.front_arms = (True, True)
    elif a == "point":
        f = back(min(1, t / 0.35))
        p.arm_r = (95 * f, 90 * f)
        p.lean = 3
        p.look = (0.8, 0)
    elif a == "think":
        p.arm_r = (-25, -160)
        p.front_arms = (False, True)
        p.head = 8 * ease(min(1, t / 0.5))
        p.look = (0.5, -0.7)
        p.symbols = ["?"] if t % 2.4 < 1.8 else []
    elif a == "sit":
        p.leg_l, p.leg_r = (-80, 5), (-80, 5)
        p.turn = 0.4
        p.dy = 14
        p.seat = True
    elif a == "cry":
        s = math.sin(t * 14) * 1.2
        p.arm_l, p.arm_r = (-20, -150), (20, 150)
        p.front_arms = (True, True)
        p.dx = s
        p.head = 6
        p.tears = True
    elif a == "laugh":
        s = math.sin(t * 16)
        p.lean = -8
        p.head = -10 + 2 * s
        p.dy = -abs(s) * 1.5
        p.arm_l, p.arm_r = (-35, -60), (35, 60)
    elif a == "shock":
        f = min(1, t / 0.25)
        p.dx = -6 * back(f)
        p.dy = -8 * math.sin(min(1, t / 0.4) * math.pi)
        p.arm_l, p.arm_r = (-140 * f, -110), (140 * f, 110)
        p.lean = -10 * f
        p.symbols = ["!"]
    elif a == "talk":
        g = math.sin(t * 3 + ph)
        p.talk = 0.5 + 0.5 * math.sin(t * 17 + ph) * (1 if (t * 1.3) % 2 < 1.5 else 0)
        p.arm_r = (55 + 20 * g, 100 + 30 * g)
        p.head = 3 * g
    elif a == "sleep":
        p.head = 18
        p.lean = 5
        p.blink = True
        p.dy = -math.sin(t * 1.4) * 1.0
    elif a == "hug":
        p.arm_l, p.arm_r = (60, 100), (85, 120)
        p.front_arms = (True, True)
        p.lean = 6
        p.turn = 0.3
    elif a == "angry":
        s = math.sin(t * 24) * 0.8
        p.dx = s
        p.arm_l, p.arm_r = (-25, -5), (25, 5)
        p.lean = 6
    elif a == "shy":
        p.arm_l, p.arm_r = (25, 40), (-25, -40)
        p.front_arms = (True, True)
        p.head = 10
        p.look = (-0.4, 0.6)
        p.dx = math.sin(t * 2) * 1.0
    elif a == "love":
        p.arm_l, p.arm_r = (-25, -150), (25, 150)
        p.front_arms = (True, True)
        p.head = -4 + 4 * math.sin(t * 3)
        p.symbols = ["heart"]
    elif a == "fall":
        f = ease(min(1, t / 0.6))
        p.lean = 70 * f
        p.dy = 8 * f
        p.arm_l, p.arm_r = (-150, -120), (150, 120)
        p.symbols = ["sweat"]
    elif a == "bow":
        f = math.sin(min(1, t / 1.2) * math.pi)
        p.lean = 35 * f
        p.arm_l, p.arm_r = (-5, -5), (5, 5)
    return p
