"""Character rig: a skeleton + one-piece outline (like ReelMimic's vector_rig).

Every character is a definition file (build/assets/cast/<id>.json) of choices (body type, colours, hair, outfit,
ears…) plus named poses and expressions. Limbs, torso, neck and head are unioned into ONE silhouette before the
outline is drawn, so joints never show seams or double outlines and limbs can't float.

Local units: the character is 100 units tall, feet at y=0, up is -y, it faces +x (the caller mirrors for left).
"""
from __future__ import annotations

import copy
import math
import re
from dataclasses import dataclass, field
from typing import Any

import skia

from .color import colors_near, find_color, mix, norm, shade

BODY_TYPES = ("chibi", "tall", "blob", "animal")
HAIR = ("none", "short", "messy", "spiky", "long", "bob", "ponytail", "bun", "twin_tails", "curly")
EYES = ("round", "dot", "big", "sleepy")
GLASSES = ("none", "round", "square", "sunglasses")
EARS = ("none", "cat", "bear", "bunny", "dog")
TAILS = ("none", "cat", "fox", "bunny")
TOPS = ("tshirt", "hoodie", "shirt", "suit", "dress", "sweater", "robe", "none")
BOTTOMS = ("pants", "shorts", "skirt", "none")
ACCESSORIES = ("beanie", "cap", "bow", "crown", "witch_hat", "party_hat", "scarf", "headphones", "backpack", "cape", "tie", "flower")
EXPRESSIONS = ("neutral", "happy", "laugh", "sad", "cry", "surprised", "angry", "love", "sleepy", "scream", "shy", "excited", "confused", "smug", "determined")
POSES = ("idle", "wave", "walk", "run", "jump", "dance", "cheer", "point", "think", "sit", "cry", "laugh", "shock", "talk",
         "sleep", "hug", "angry", "shy", "love", "fall", "clap", "bow")

DEFAULT = {
    "body": "chibi", "height": 1.0, "build": "normal",
    "colors": {"skin": "#FFD9B8", "hair": "#3B2A20", "top": "#4A7BF7", "bottom": "#2F3A56", "shoes": "#2B2B30",
               "accent": "#FFD54F", "line": "#2A2430", "cheek": "#FF9AA2", "eyes": "#2A2430"},
    "hair": "short", "eyes": "round", "glasses": "none", "ears": "none", "tail": "none", "top": "tshirt", "bottom": "pants",
    "accessories": [], "blush": True, "freckles": False,
    "expressions": ["neutral", "happy", "laugh", "sad", "surprised", "angry", "love", "shy", "scream"],
    "poses": ["idle", "wave", "walk", "jump", "point", "cheer", "think"],
}


def _pick(v: Any, allowed: tuple, default: str) -> str:
    s = str(v or "").strip().lower().replace("-", "_").replace(" ", "_")
    return s if s in allowed else default


def normalize(c: dict | None, fallback_id: str = "hero", name: str | None = None) -> dict:
    """Coerce any (LLM-written) definition into a valid one."""
    c = dict(c or {})
    out = copy.deepcopy(DEFAULT)
    out["id"] = re.sub(r"[^\w-]+", "_", str(c.get("id") or fallback_id))[:32] or fallback_id
    out["name"] = str(c.get("name") or name or out["id"])[:40]
    out["design"] = str(c.get("design") or "")[:400]
    out["body"] = _pick(c.get("body") or c.get("body_type"), BODY_TYPES, "chibi")
    try:
        out["height"] = max(0.55, min(1.5, float(c.get("height") or 1.0)))
    except (TypeError, ValueError):
        pass
    out["build"] = _pick(c.get("build"), ("slim", "normal", "round"), "normal")
    cols = c.get("colors") if isinstance(c.get("colors"), dict) else {}
    for k, v in DEFAULT["colors"].items():
        out["colors"][k] = norm(cols.get(k), v) if cols.get(k) else v
    out["hair"] = _pick(c.get("hair") if not isinstance(c.get("hair"), dict) else c["hair"].get("style"), HAIR, "short")
    out["eyes"] = _pick(c.get("eyes"), EYES, "round")
    out["glasses"] = _pick(c.get("glasses") if c.get("glasses") not in (True, False) else ("round" if c.get("glasses") else "none"), GLASSES, "none")
    out["ears"] = _pick(c.get("ears"), EARS, "none")
    out["tail"] = _pick(c.get("tail"), TAILS, "none")
    out["top"] = _pick(c.get("top") or c.get("outfit"), TOPS, "tshirt")
    out["bottom"] = _pick(c.get("bottom"), BOTTOMS, "pants")
    acc = c.get("accessories") or []
    out["accessories"] = [a for a in (_pick(x, ACCESSORIES, "") for x in (acc if isinstance(acc, list) else [acc])) if a][:4]
    out["blush"] = bool(c.get("blush", True))
    out["freckles"] = bool(c.get("freckles", False))
    for key, allowed in (("expressions", EXPRESSIONS), ("poses", POSES)):
        vals = [x for x in (str(v).lower() for v in c.get(key) or []) if x in allowed]
        out[key] = list(dict.fromkeys(vals + DEFAULT[key]))[:12]
    if out["top"] == "dress":
        out["bottom"] = "none"
    if out["body"] == "blob":
        out["top"] = "none" if out["top"] in ("tshirt", "none") else out["top"]
    return out


def from_description(cid: str, name: str, design: str) -> dict:
    """A first definition from a plain description (used when no AI is available, and as the AI's starting point)."""
    t = (design or "").lower() + " " + (name or "").lower()
    d: dict[str, Any] = {"id": cid, "name": name, "design": design}
    if re.search(r"mochi|麻糬|blob|slime|bean|豆|團子|丸", t):
        d["body"] = "blob"
    elif re.search(r"cat|kitten|貓|猫|dog|puppy|狗|bear|熊|bunny|rabbit|兔|fox|狐", t):
        d["body"] = "animal"
    elif re.search(r"tall|adult|teacher|mom|dad|grandpa|grandma|大人|媽|爸|老師|父|母|man|woman", t):
        d["body"] = "tall"
    else:
        d["body"] = "chibi"
    d["ears"] = "cat" if re.search(r"cat|kitten|貓|猫", t) else "bear" if re.search(r"bear|熊", t) else "bunny" if re.search(r"bunny|rabbit|兔", t) else "dog" if re.search(r"dog|puppy|狗", t) else "none"
    d["tail"] = {"cat": "cat", "bunny": "bunny"}.get(d["ears"], "fox" if re.search(r"fox|狐", t) else "none")
    hair = "short"
    for pat, h in ((r"messy|亂髮|乱发|bedhead", "messy"), (r"spiky|刺蝟|刺猬", "spiky"), (r"ponytail|馬尾|马尾", "ponytail"),
                   (r"twin|雙馬尾|双马尾|pigtail", "twin_tails"), (r"\bbun\b|丸子頭|包包頭", "bun"), (r"curly|捲髮|卷发|afro", "curly"),
                   (r"\bbob\b|鮑伯|妹妹頭", "bob"), (r"long\b[^,，、]*hair|長髮|长发", "long"), (r"bald|光頭|光头|no hair", "none")):
        if re.search(pat, t):
            hair = pat and h
            break
    female = bool(re.search(r"\b(girl|woman|lady|she|her|princess|queen|mom|mother|sister|grandma|daughter|wife|girlfriend|actress)\b|女孩|女生|女人|小女|她|公主|媽|妈|姐|妹|奶奶|阿姨", t))
    if female and hair == "short" and not re.search(r"short hair|短髮|短发", t):
        hair = "ponytail" if re.search(r"sport|run|active|運動|运动", t) else "long"
    if d["body"] in ("blob", "animal") and hair in ("short", "long", "ponytail") and not re.search(r"hair|髮|发", t):
        hair = "messy" if "亂" in t or "messy" in t else "none"
    d["hair"] = hair
    d["_female"] = female
    d["glasses"] = "sunglasses" if re.search(r"sunglass|墨鏡|墨镜", t) else "round" if re.search(r"glasses|眼鏡|眼镜|spectacle", t) else "none"
    top = "tshirt"
    for pat, v in ((r"hoodie|連帽|连帽|帽t|帽T|raincoat|jacket|coat|parka|外套|雨衣", "hoodie"), (r"suit|西裝|西装|blazer", "suit"), (r"dress|洋裝|裙子|连衣裙|gown", "dress"),
                   (r"sweater|毛衣|knit", "sweater"), (r"shirt|襯衫|衬衫", "shirt"), (r"robe|袍|kimono|和服", "robe")):
        if re.search(pat, t):
            top = v
            break
    clothed = re.search(r"hoodie|連帽|连帽|suit|西裝|dress|洋裝|裙|sweater|毛衣|shirt|襯衫|robe|袍|kimono|jacket|coat|外套|雨衣|t-shirt|tee|衣|pants|褲|jeans|overalls|uniform", t)
    if top == "tshirt" and d.pop("_female", False) and not clothed and d["body"] not in ("animal", "blob"):
        top = "dress"
    d.pop("_female", None)
    d["top"] = top if (clothed or d["body"] not in ("animal", "blob")) else "none"
    d["bottom"] = "none" if not clothed and d["body"] in ("animal", "blob") else "skirt" if re.search(r"skirt|裙", t) and top != "dress" else "shorts" if re.search(r"shorts|短褲|短裤", t) else "pants"
    acc = [a for pat, a in ((r"beanie|毛帽", "beanie"), (r"\bcap\b|棒球帽|鴨舌帽", "cap"), (r"\bbow\b|蝴蝶結|蝴蝶结", "bow"), (r"crown|王冠|皇冠", "crown"),
                            (r"witch|巫師帽|巫婆", "witch_hat"), (r"scarf|圍巾|围巾", "scarf"), (r"headphone|耳機|耳机", "headphones"),
                            (r"backpack|背包|書包", "backpack"), (r"cape|披風|斗篷", "cape"), (r"\btie\b|領帶|领带", "tie"), (r"flower|花", "flower")) if re.search(pat, t)]
    d["accessories"] = acc
    skin = colors_near(t, ["skin", "膚", "肤", "body", "身體"]) or ("#B9A8CF" if re.search(r"灰紫", t) else None)
    colors = {
        "skin": skin or ("#F2E6D8" if d["body"] in ("blob",) else "#FFD9B8"),
        "hair": colors_near(t, ["hair", "髮", "发"]) or "#3B2A20",
        "top": colors_near(t, ["raincoat", "coat", "hoodie", "shirt", "連帽", "帽t", "dress", "洋裝", "sweater", "毛衣", "suit", "西裝", "jacket", "外套", "雨衣", "top", "uniform", "衣"]) or ("#F0628F" if d["top"] == "dress" else ["#4A7BF7", "#FFB300", "#26A69A", "#7E57C2", "#EF5350", "#F0628F"][sum(map(ord, cid)) % 6]),
        "bottom": colors_near(t, ["pants", "褲", "skirt", "裙", "shorts", "jeans", "trousers"]) or "#2F3A56",
        "shoes": colors_near(t, ["boots", "shoes", "sneakers", "鞋", "靴"]) or "#2B2B30",
    }
    if d["body"] == "animal" and not skin:
        colors["skin"] = "#F2B66D" if re.search(r"fox|狐|orange|橘", t) else "#E8E2DA" if re.search(r"white|白|bunny|兔", t) else "#C08A5B" if re.search(r"bear|熊|dog|狗", t) else "#F6C27A"
    acc_c = colors_near(t, ["scarf", "圍巾", "围巾", "bow", "蝴蝶結", "hat", "帽", "cap", "cape", "披風", "backpack", "背包", "headphone", "耳機", "tie", "領帶", "crown", "flower"])
    if acc_c:
        colors["accent"] = acc_c
    d["colors"] = colors
    return normalize(d)


# ---------- geometry ----------
PROP = {
    "chibi": dict(head_r=24, head_y=-74, neck=(-53, -48), torso=(-52, -22), sh=12, hip=7.5, arm=(13, 12), arm_w=8.5, hand=5.2,
                  leg=(11.5, 10.5), leg_w=9.5, foot=(8.5, 4.6), sh_y=-48),
    "tall": dict(head_r=12.5, head_y=-86, neck=(-76, -72), torso=(-75, -44), sh=15, hip=7.5, arm=(20, 19), arm_w=7.2, hand=4.3,
                 leg=(23, 21), leg_w=8.6, foot=(10, 4.6), sh_y=-71),
    "animal": dict(head_r=25, head_y=-72, neck=(-51, -46), torso=(-50, -21), sh=12, hip=7.5, arm=(12, 11), arm_w=9, hand=5.6,
                   leg=(10.5, 10), leg_w=10, foot=(8.5, 5), sh_y=-46),
    "blob": dict(head_r=27, head_y=-46, neck=(-40, -40), torso=(-74, 0), sh=35, hip=15, arm=(12, 10), arm_w=8.5, hand=5.6,
                 leg=(3, 3), leg_w=10, foot=(9.5, 5.2), sh_y=-40),
}


def _rot(p: tuple[float, float], o: tuple[float, float], deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    x, y = p[0] - o[0], p[1] - o[1]
    return (o[0] + x * math.cos(a) - y * math.sin(a), o[1] + x * math.sin(a) + y * math.cos(a))


def _dir(deg: float) -> tuple[float, float]:
    a = math.radians(deg)
    return (math.sin(a), math.cos(a))


def _limb(points: list[tuple[float, float]], w: float) -> skia.Path:
    src = skia.Path()
    src.moveTo(*points[0])
    for p in points[1:]:
        src.lineTo(*p)
    paint = skia.Paint(Style=skia.Paint.kStroke_Style, StrokeWidth=w, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)
    dst = skia.Path()
    paint.getFillPath(src, dst)
    return dst


def _oval(cx: float, cy: float, rx: float, ry: float) -> skia.Path:
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return p


def _union(paths: list[skia.Path]) -> skia.Path:
    b = skia.OpBuilder()
    for p in paths:
        if p is not None and not p.isEmpty():
            b.add(p, skia.PathOp.kUnion_PathOp)
    out = b.resolve()
    return out if out is not None else skia.Path()


def _rrect_trap(top_y: float, bot_y: float, top_w: float, bot_w: float, r: float) -> skia.Path:
    p = skia.Path()
    tl, tr = (-top_w / 2, top_y), (top_w / 2, top_y)
    br, bl = (bot_w / 2, bot_y), (-bot_w / 2, bot_y)
    p.moveTo(tl[0] + r, tl[1])
    p.lineTo(tr[0] - r, tr[1])
    p.quadTo(tr[0], tr[1], tr[0] + (br[0] - tr[0]) * 0.15, tr[1] + r)
    p.lineTo(br[0], br[1] - r)
    p.quadTo(br[0], br[1], br[0] - r, br[1])
    p.lineTo(bl[0] + r, bl[1])
    p.quadTo(bl[0], bl[1], bl[0], bl[1] - r)
    p.lineTo(tl[0] - (tl[0] - bl[0]) * 0.15, tl[1] + r)
    p.quadTo(tl[0], tl[1], tl[0] + r, tl[1])
    p.close()
    return p


@dataclass
class Pose:
    lean: float = 0.0
    head: float = 0.0
    arm_l: tuple[float, float] = (-12.0, -6.0)    # absolute screen angles (deg): upper arm, forearm (0 = down, + = toward +x)
    arm_r: tuple[float, float] = (12.0, 6.0)
    leg_l: tuple[float, float] = (-3.0, -3.0)
    leg_r: tuple[float, float] = (3.0, 3.0)
    dx: float = 0.0
    dy: float = 0.0
    squash: float = 0.0
    turn: float = 0.0
    look: tuple[float, float] = (0.0, 0.0)
    blink: bool = False
    talk: float = 0.0
    front_arms: tuple[bool, bool] = (False, False)   # draw this arm over the body (hand at chin, hug…)
    symbols: list[str] = field(default_factory=list)
    tears: bool = False
    seat: bool = False


@dataclass
class Drawn:
    bounds: skia.Rect
    head: skia.Rect
    silhouette: skia.Path


def _hair_back(cd: dict, cx: float, cy: float, r: float, turn: float) -> skia.Path | None:
    h = cd["hair"]
    if h == "long":
        p = skia.Path()
        p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(cx - r * 1.05, cy - r * 0.6, cx + r * 1.05 - turn * r * 0.4, cy + r * 1.35), r * 0.5, r * 0.5))
        return p
    if h == "ponytail":
        return _oval(cx - r * (0.95 + 0.2 * turn), cy - r * 0.1, r * 0.38, r * 0.72)
    if h == "twin_tails":
        return _union([_oval(cx - r * 1.12, cy + r * 0.15, r * 0.34, r * 0.75), _oval(cx + r * 1.12, cy + r * 0.15, r * 0.34, r * 0.75)])
    if h == "bun":
        return _oval(cx - turn * r * 0.2, cy - r * 1.02, r * 0.42, r * 0.36)
    if h == "bob":
        p = skia.Path()
        p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(cx - r * 1.12, cy - r * 1.05, cx + r * 1.12, cy + r * 0.55), r * 0.8, r * 0.8))
        return p
    if h == "curly":
        return _union([_oval(cx + math.cos(a) * r * 0.95, cy - r * 0.15 + math.sin(a) * r * 0.95, r * 0.34, r * 0.34)
                       for a in [math.pi * (1.0 + i / 7) for i in range(8)]])
    return None


def _hair_front(cd: dict, cx: float, cy: float, r: float, turn: float, seed: int = 0) -> skia.Path | None:
    h = cd["hair"]
    if h == "none":
        return None
    off = turn * r * 0.25
    p = skia.Path()
    if h in ("short", "ponytail", "bun", "long", "twin_tails", "bob", "curly"):
        # cap over the top of the head with a scalloped fringe
        p.moveTo(cx - r * 1.04, cy - r * 0.05)
        p.cubicTo(cx - r * 1.1, cy - r * 1.25, cx + r * 1.1, cy - r * 1.25, cx + r * 1.04, cy - r * 0.05)
        n = 4
        x0, x1 = cx + r * 1.04, cx - r * 1.04
        for i in range(n):
            xa = x0 + (x1 - x0) * i / n
            xb = x0 + (x1 - x0) * (i + 1) / n
            p.quadTo((xa + xb) / 2 + off, cy - r * (0.28 if i % 2 else 0.42), xb, cy - r * (0.35 if i < n - 1 else 0.05))
        p.close()
        return p
    if h in ("messy", "spiky"):
        spikes = 9 if h == "messy" else 6
        p.moveTo(cx - r * 1.02, cy - r * 0.2)
        for i in range(spikes + 1):
            a = math.pi * (1.05 + 0.9 * i / spikes)
            rr = r * ((1.42 if i % 2 == 0 else 1.06) if h == "spiky" else (1.16 + 0.06 * ((i * 37 + seed) % 3) if i % 2 == 0 else 0.99))
            p.lineTo(cx + math.cos(a) * rr + off, cy - r * 0.15 + math.sin(a) * rr)
        p.lineTo(cx + r * 1.02, cy - r * 0.2)
        p.quadTo(cx + off, cy - r * (0.62 if h == "spiky" else 0.5), cx - r * 1.02, cy - r * 0.2)
        p.close()
        return p
    return None


def _ears(cd: dict, cx: float, cy: float, r: float) -> list[tuple[skia.Path, skia.Path | None]]:
    e = cd["ears"]
    out = []
    for s in (-1, 1):
        if e == "cat":
            p = skia.Path()
            p.moveTo(cx + s * r * 0.95, cy - r * 0.35)
            p.lineTo(cx + s * r * 0.82, cy - r * 1.32)
            p.lineTo(cx + s * r * 0.25, cy - r * 0.88)
            p.close()
            q = skia.Path()
            q.moveTo(cx + s * r * 0.8, cy - r * 0.55)
            q.lineTo(cx + s * r * 0.76, cy - r * 1.08)
            q.lineTo(cx + s * r * 0.42, cy - r * 0.86)
            q.close()
            out.append((p, q))
        elif e == "bear":
            out.append((_oval(cx + s * r * 0.78, cy - r * 0.85, r * 0.34, r * 0.34), _oval(cx + s * r * 0.78, cy - r * 0.85, r * 0.17, r * 0.17)))
        elif e == "bunny":
            out.append((_oval(cx + s * r * 0.42, cy - r * 1.55, r * 0.22, r * 0.72), _oval(cx + s * r * 0.42, cy - r * 1.5, r * 0.1, r * 0.5)))
        elif e == "dog":
            out.append((_oval(cx + s * r * 1.02, cy - r * 0.15, r * 0.24, r * 0.55), None))
    return out


def draw(pen, cd: dict, pose: Pose, expr: str, t: float = 0.0, symbols: bool = True) -> Drawn:
    """Draw the character in local units (100 tall, feet at 0, facing +x). Returns local bounds."""
    c = pen.c
    K = PROP[cd["body"]]
    col = cd["colors"]
    lw = 2.3 if cd["body"] != "tall" else 2.0
    build_k = {"slim": 0.86, "normal": 1.0, "round": 1.18}[cd["build"]]
    turn = max(0.0, min(1.0, pose.turn))
    c.save()
    # squash & stretch about the feet, plus root offset (jump, bob)
    c.translate(pose.dx, pose.dy)
    if pose.squash:
        c.scale(1 + pose.squash * 0.5, 1 - pose.squash)
    hip_c = (0.0, K["torso"][1] if cd["body"] != "blob" else -20.0)

    def up(p: tuple[float, float]) -> tuple[float, float]:   # upper body leans about the hips
        return _rot(p, hip_c, pose.lean)

    side_k = 1 - 0.45 * turn
    # ---- legs ----
    leg_paths, feet, leg_parts = [], [], []
    for side, (h, k) in ((-1, pose.leg_l), (1, pose.leg_r)):
        hip = (side * K["hip"] * side_k * build_k, K["torso"][1] - 2 if cd["body"] != "blob" else -6)
        if cd["body"] == "blob":
            knee = hip
            ankle = (hip[0] + _dir(h)[0] * 4, hip[1] + 4)
        else:
            d1, d2 = _dir(h), _dir(k)
            knee = (hip[0] + d1[0] * K["leg"][0], hip[1] + d1[1] * K["leg"][0])
            ankle = (knee[0] + d2[0] * K["leg"][1], knee[1] + d2[1] * K["leg"][1])
        lp = _limb([hip, knee, ankle], K["leg_w"])
        thigh = _limb([hip, knee], K["leg_w"])
        foot = _oval(ankle[0] + K["foot"][0] * 0.35 * (1 if turn > 0.3 else 0.15 * side), ankle[1] + 0.5, K["foot"][0], K["foot"][1])
        leg_paths.append(lp)
        feet.append(foot)
        leg_parts.append((lp, thigh, foot))
    # ---- torso ----
    t0, t1 = K["torso"]
    if cd["body"] == "blob":
        torso = _oval(0, -38, 40 * build_k * (1 - 0.08 * turn), 38)
    else:
        tw, bw = 2 * K["sh"] * build_k * (1 - 0.25 * turn), 2 * (K["hip"] + 6) * build_k * (1 - 0.2 * turn)
        torso = _rrect_trap(t0, t1, tw, bw, 6)
        if pose.lean:
            m = skia.Matrix.RotateDeg(pose.lean, skia.Point(*hip_c))
            torso.transform(m)
    neck_path = None
    if cd["body"] != "blob":
        n0, n1 = K["neck"]
        neck_path = skia.Path()
        nw = K["head_r"] * (0.34 if cd["body"] != "tall" else 0.5)
        neck_path.addRect(skia.Rect.MakeLTRB(-nw / 2, n0 - 6, nw / 2, n1 + 4))
        if pose.lean:
            neck_path.transform(skia.Matrix.RotateDeg(pose.lean, skia.Point(*hip_c)))
    # ---- head ----
    hr = K["head_r"]
    head_c = up((turn * hr * 0.12, K["head_y"]))
    if cd["body"] == "blob":
        head_c = (turn * 3.0, -46.0)
    head_path = _oval(head_c[0], head_c[1], hr * (1.08 if cd["body"] != "tall" else 0.92) * (1 - 0.06 * turn), hr)
    if pose.head:
        head_path.transform(skia.Matrix.RotateDeg(pose.head, skia.Point(head_c[0], head_c[1] + hr * 0.8)))
    # ---- arms ----
    arms = []
    for idx, (side, (a1, a2)) in enumerate(((-1, pose.arm_l), (1, pose.arm_r))):
        sh = up((side * (K["sh"] - 3) * side_k * build_k, K["sh_y"]))
        d1, d2 = _dir(a1), _dir(a2)
        el = (sh[0] + d1[0] * K["arm"][0], sh[1] + d1[1] * K["arm"][0])
        hd = (el[0] + d2[0] * K["arm"][1], el[1] + d2[1] * K["arm"][1])
        path = _limb([sh, el, hd], K["arm_w"])
        upper = _limb([sh, el], K["arm_w"])
        hand = _oval(hd[0], hd[1], K["hand"], K["hand"])
        front = pose.front_arms[idx] or (turn > 0.3 and side == 1)
        behind = turn > 0.3 and side == -1
        arms.append(dict(side=side, sh=sh, path=path, upper=upper, hand=hand, front=front, behind=behind))
    # ---- extras behind the body ----
    sil_parts = list(leg_paths) + feet + [torso, head_path] + ([neck_path] if neck_path else [])
    ear_list = _ears(cd, head_c[0], head_c[1], hr)
    for ep, _ in ear_list:
        sil_parts.append(ep)
    hb = _hair_back(cd, head_c[0], head_c[1], hr, turn)
    if hb is not None:
        sil_parts.append(hb)
    tail = None
    if cd["tail"] != "none":
        tail = skia.Path()
        bx, by = -K["hip"] - 4, t1 - 6 if cd["body"] != "blob" else -14
        if cd["tail"] == "bunny":
            tail = _oval(bx - 3, by, 6, 6)
        elif cd["tail"] == "fox":
            tail = _oval(bx - 12, by - 8, 13, 7)
            tail.transform(skia.Matrix.RotateDeg(-35 + 8 * math.sin(t * 3), skia.Point(bx, by)))
        else:
            tail = _limb([(bx, by), (bx - 10, by - 6 + 3 * math.sin(t * 4)), (bx - 13, by - 18)], 4.5)
        sil_parts.append(tail)
    for a in arms:
        if not a["front"] and not a["behind"]:
            sil_parts += [a["path"], a["hand"]]
    silhouette = _union(sil_parts)
    # cape / backpack sit behind everything
    if "cape" in cd["accessories"] and cd["body"] != "blob":
        cape = skia.Path()
        cape.moveTo(-K["sh"] * 1.0, K["sh_y"] - 2)
        cape.lineTo(K["sh"] * 1.0, K["sh_y"] - 2)
        cape.lineTo(K["sh"] * 1.5 + 3 * math.sin(t * 2), t1 + 12)
        cape.lineTo(-K["sh"] * 1.5 + 3 * math.sin(t * 2 + 1), t1 + 12)
        cape.close()
        pen.shape(cape, col["accent"], lw)
    if "backpack" in cd["accessories"] and cd["body"] != "blob":
        bp = skia.Path()
        bp.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-K["sh"] * 1.1 - 4 * turn, t0 + 2, K["sh"] * 0.4, t1 - 2), 5, 5))
        pen.shape(bp, col["accent"], lw)
    # ---- behind arm ----
    for a in arms:
        if a["behind"]:
            u = _union([a["path"], a["hand"]])
            pen.outline(u, lw)
            pen.fill(a["path"], shade(_sleeve(cd, upper=False), -0.08))
            pen.fill(a["upper"], shade(_sleeve(cd, upper=True), -0.08))
            pen.fill(a["hand"], shade(col["skin"], -0.06))
    # ---- silhouette outline, then the fills ----
    pen.outline(silhouette, lw)
    if tail is not None:
        pen.fill(tail, col["hair"] if cd["body"] != "animal" else col["skin"])
    if hb is not None:
        pen.fill(hb, col["hair"])
    for ep, inner in ear_list:
        pen.fill(ep, col["hair"] if cd["body"] not in ("animal", "blob") and cd["ears"] != "none" and cd["hair"] != "none" else col["skin"])
        if inner is not None:
            pen.fill(inner, mix(col["skin"], col["cheek"], 0.55), flat=True)
    for lp, thigh, foot in leg_parts:
        if cd["bottom"] == "pants":
            pen.fill(lp, col["bottom"])
        elif cd["bottom"] == "shorts":
            pen.fill(lp, col["skin"])
            pen.fill(thigh, col["bottom"])
        else:
            pen.fill(lp, col["skin"])
        pen.fill(foot, col["shoes"])
    if neck_path is not None:
        pen.fill(neck_path, shade(col["skin"], -0.05))
    if cd["body"] == "blob":
        pen.fill(torso, col["skin"])
        if cd["top"] not in ("none",):
            belly = skia.Path()
            belly.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-34, -30, 34, -1), 14, 14))
            belly2 = skia.Op(belly, torso, skia.PathOp.kIntersect_PathOp) or skia.Path()
            pen.fill(belly2, col["top"])
    else:
        torso_col = col["top"] if cd["top"] != "none" else col["skin"]
        pen.fill(torso, torso_col)
        if cd["top"] == "dress" or cd["bottom"] == "skirt":
            sk = skia.Path()
            y0 = t1 - 9 if cd["top"] != "dress" else (t0 + t1) / 2 + 3
            sk.moveTo(-K["hip"] - 5, y0)
            sk.lineTo(K["hip"] + 5, y0)
            sk.lineTo(K["hip"] + 13, t1 + 9)
            sk.quadTo(0, t1 + 12, -K["hip"] - 13, t1 + 9)
            sk.close()
            if pose.lean:
                sk.transform(skia.Matrix.RotateDeg(pose.lean, skia.Point(*hip_c)))
            pen.shape(sk, col["top"] if cd["top"] == "dress" else col["bottom"], lw)
        _torso_details(pen, cd, K, hip_c, pose, lw)
    for a in arms:
        if not a["front"] and not a["behind"]:
            pen.fill(a["path"], _sleeve(cd, upper=False))
            pen.fill(a["upper"], _sleeve(cd, upper=True))
            pen.fill(a["hand"], col["skin"])
    # head
    pen.fill(head_path, col["skin"])
    if cd["body"] == "blob":
        pass
    _face(pen, cd, head_c, hr, pose, expr, t, lw)
    hf = _hair_front(cd, head_c[0], head_c[1], hr, turn, seed=len(cd["id"]))
    if hf is not None:
        if pose.head:
            hf.transform(skia.Matrix.RotateDeg(pose.head, skia.Point(head_c[0], head_c[1] + hr * 0.8)))
        if cd["hair"] in ("messy", "spiky"):
            pen.shape(hf, col["hair"], lw)
        else:
            clip = skia.Op(hf, _oval(head_c[0], head_c[1], hr * 1.2, hr * 1.12), skia.PathOp.kIntersect_PathOp) or skia.Path()
            pen.shape(clip, col["hair"], lw * 0.8)
    _head_accessories(pen, cd, head_c, hr, lw, t)
    # front arms
    for a in arms:
        if a["front"]:
            u = _union([a["path"], a["hand"]])
            pen.outline(u, lw)
            pen.fill(a["path"], _sleeve(cd, upper=False))
            pen.fill(a["upper"], _sleeve(cd, upper=True))
            pen.fill(a["hand"], col["skin"])
            patch = _oval(a["sh"][0], a["sh"][1], K["arm_w"] * 0.62, K["arm_w"] * 0.62)
            pen.fill(patch, _sleeve(cd, upper=True), flat=True)
    if symbols:
        _symbols(pen, cd, head_c, hr, pose, expr, t, lw)
    bounds = silhouette.computeTightBounds()
    head_b = head_path.computeTightBounds()
    c.restore()
    m = skia.Matrix()
    m.preTranslate(pose.dx, pose.dy)
    if pose.squash:
        m.preScale(1 + pose.squash * 0.5, 1 - pose.squash)
    return Drawn(bounds=m.mapRect(bounds), head=m.mapRect(head_b), silhouette=silhouette)


def _sleeve(cd: dict, upper: bool) -> str:
    col = cd["colors"]
    if cd["body"] == "blob" or cd["top"] == "none":
        return col["skin"]
    if cd["top"] in ("tshirt", "dress"):
        return col["top"] if upper else col["skin"]
    return col["top"]


def _torso_details(pen, cd: dict, K: dict, hip_c, pose: Pose, lw: float) -> None:
    col = cd["colors"]
    t0, t1 = K["torso"]
    c = pen.c
    c.save()
    if pose.lean:
        c.rotate(pose.lean, hip_c[0], hip_c[1])
    if cd["top"] == "hoodie":
        hood = skia.Path()
        hood.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-K["sh"] * 0.75, t0 - 3, K["sh"] * 0.75, t0 + 5), 4, 4))
        pen.shape(hood, shade(col["top"], -0.1), lw * 0.7)
        for s in (-1, 1):
            st = skia.Path()
            st.moveTo(s * 3, t0 + 4)
            st.lineTo(s * 3.5, t0 + 12)
            pen.line(st, "#FFFFFF", 1.4)
        pocket = skia.Path()
        pocket.moveTo(-K["sh"] * 0.55, t1 - 9)
        pocket.lineTo(K["sh"] * 0.55, t1 - 9)
        pen.line(pocket, shade(col["top"], -0.25), 1.2)
    elif cd["top"] in ("shirt", "suit"):
        for s in (-1, 1):
            col_p = skia.Path()
            col_p.moveTo(0, t0 + 1)
            col_p.lineTo(s * 6, t0 - 1)
            col_p.lineTo(s * 4, t0 + 6)
            col_p.close()
            pen.shape(col_p, "#FFFFFF", lw * 0.6)
        if cd["top"] == "suit" or "tie" in cd["accessories"]:
            tie = skia.Path()
            tie.moveTo(-2, t0 + 3)
            tie.lineTo(2, t0 + 3)
            tie.lineTo(3, t0 + 15)
            tie.lineTo(0, t0 + 19)
            tie.lineTo(-3, t0 + 15)
            tie.close()
            pen.shape(tie, col["accent"], lw * 0.5)
    elif cd["top"] == "sweater":
        st = skia.Path()
        st.moveTo(-K["sh"], (t0 + t1) / 2)
        st.lineTo(K["sh"], (t0 + t1) / 2)
        pen.line(st, col["accent"], 2.2)
    elif cd["top"] == "robe":
        st = skia.Path()
        st.moveTo(-5, t0)
        st.lineTo(4, t1 - 4)
        pen.line(st, shade(col["top"], -0.25), 1.6)
    if "scarf" in cd["accessories"]:
        sc = skia.Path()
        sc.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(-K["sh"] * 0.8, t0 - 4, K["sh"] * 0.8, t0 + 3), 3, 3))
        pen.shape(sc, col["accent"], lw * 0.7)
    c.restore()


def _head_accessories(pen, cd: dict, hc, r: float, lw: float, t: float) -> None:
    col = cd["colors"]
    cx, cy = hc
    acc = cd["accessories"]
    if "headphones" in acc:
        band = skia.Path()
        band.addArc(skia.Rect.MakeLTRB(cx - r * 1.08, cy - r * 1.12, cx + r * 1.08, cy + r * 0.9), 195, 150)
        pen.line(band, col["accent"], 3.2)
        for s in (-1, 1):
            pen.shape(_oval(cx + s * r * 1.02, cy + r * 0.05, r * 0.2, r * 0.3), col["accent"], lw * 0.7)
    if "beanie" in acc:
        b = skia.Path()
        b.addArc(skia.Rect.MakeLTRB(cx - r * 1.05, cy - r * 1.25, cx + r * 1.05, cy + r * 0.6), 180, 180)
        b.close()
        pen.shape(b, col["accent"], lw)
        pen.shape(_oval(cx, cy - r * 1.22, r * 0.18, r * 0.18), "#FFFFFF", lw * 0.6)
    if "cap" in acc:
        b = skia.Path()
        b.addArc(skia.Rect.MakeLTRB(cx - r, cy - r * 1.18, cx + r, cy + r * 0.5), 180, 180)
        b.close()
        pen.shape(b, col["accent"], lw)
        brim = skia.Path()
        brim.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(cx, cy - r * 0.42, cx + r * 1.45, cy - r * 0.26), 3, 3))
        pen.shape(brim, shade(col["accent"], -0.12), lw * 0.8)
    if "bow" in acc:
        for s in (-1, 1):
            w = skia.Path()
            w.moveTo(cx + r * 0.55, cy - r * 0.9)
            w.lineTo(cx + r * 0.55 + s * r * 0.4, cy - r * 1.15)
            w.lineTo(cx + r * 0.55 + s * r * 0.4, cy - r * 0.65)
            w.close()
            pen.shape(w, col["accent"], lw * 0.7)
        pen.shape(_oval(cx + r * 0.55, cy - r * 0.9, r * 0.1, r * 0.1), shade(col["accent"], -0.1), lw * 0.6)
    if "flower" in acc:
        for i in range(5):
            a = i * 2 * math.pi / 5
            pen.shape(_oval(cx - r * 0.6 + math.cos(a) * r * 0.16, cy - r * 0.85 + math.sin(a) * r * 0.16, r * 0.12, r * 0.12), col["accent"], lw * 0.5)
        pen.fill(_oval(cx - r * 0.6, cy - r * 0.85, r * 0.08, r * 0.08), "#FFD54F", flat=True)
    if "crown" in acc:
        cr = skia.Path()
        cr.moveTo(cx - r * 0.5, cy - r * 0.95)
        for i, (dx, dy) in enumerate(((-0.5, -1.45), (-0.25, -1.15), (0, -1.55), (0.25, -1.15), (0.5, -1.45), (0.5, -0.95))):
            cr.lineTo(cx + r * dx, cy + r * dy)
        cr.close()
        pen.shape(cr, "#F4B400", lw * 0.8)
    if "witch_hat" in acc:
        h = skia.Path()
        h.moveTo(cx - r * 1.3, cy - r * 0.75)
        h.lineTo(cx + r * 1.3, cy - r * 0.75)
        h.lineTo(cx + r * 0.6, cy - r * 0.95)
        h.lineTo(cx + r * 0.25 + 3 * math.sin(t), cy - r * 2.2)
        h.lineTo(cx - r * 0.6, cy - r * 0.95)
        h.close()
        pen.shape(h, col["accent"] if cd["colors"]["accent"] != "#FFD54F" else "#3B2A5E", lw)
    if "party_hat" in acc:
        h = skia.Path()
        h.moveTo(cx - r * 0.45, cy - r * 0.9)
        h.lineTo(cx + r * 0.45, cy - r * 0.9)
        h.lineTo(cx + r * 0.05, cy - r * 1.9)
        h.close()
        pen.shape(h, col["accent"], lw)


def _eye_path_open(x: float, y: float, rx: float, ry: float) -> skia.Path:
    return _oval(x, y, rx, ry)


def _face(pen, cd: dict, hc, r: float, pose: Pose, expr: str, t: float, lw: float) -> None:
    col = cd["colors"]
    cx, cy = hc
    turn = pose.turn
    ink = col["eyes"]
    c = pen.c
    c.save()
    if pose.head:
        c.rotate(pose.head, cx, cy + r * 0.8)
    fx = cx + turn * r * 0.38
    ey = cy + r * (0.02 if cd["body"] != "tall" else -0.05)
    ex = r * (0.4 if cd["body"] != "tall" else 0.36)
    big = cd["eyes"] == "big"
    eye_r = r * (0.17 if big else 0.13 if cd["eyes"] == "round" else 0.09)
    sides = [(-1, 1 - 0.55 * turn), (1, 1 + 0.12 * turn)] if turn < 0.85 else [(1, 0.9)]
    lx, ly = pose.look
    e = expr
    blink = pose.blink and e not in ("laugh", "sleepy", "cry", "love", "excited", "scream")
    for s, k in sides:
        x = fx + s * ex * k * (1 - 0.3 * turn)
        y = ey
        if blink or e in ("sleepy",):
            p = skia.Path()
            p.moveTo(x - eye_r * k, y)
            p.quadTo(x, y + eye_r * 0.6, x + eye_r * k, y)
            pen.line(p, ink, 1.8)
        elif e == "laugh":
            p = skia.Path()
            p.moveTo(x - eye_r * 1.1 * k, y + eye_r * 0.3)
            p.quadTo(x, y - eye_r * 1.3, x + eye_r * 1.1 * k, y + eye_r * 0.3)
            pen.line(p, ink, 2.0)
        elif e == "cry":
            p = skia.Path()
            p.moveTo(x - eye_r * 1.1 * k, y - eye_r * 0.2)
            p.quadTo(x, y + eye_r * 0.9, x + eye_r * 1.1 * k, y - eye_r * 0.2)
            pen.line(p, ink, 2.0)
        elif e == "love":
            hp = _heart(x, y, eye_r * 1.5)
            pen.shape(hp, "#E5484D", 0.8)
        elif e == "excited":
            pen.shape(_star(x, y, eye_r * 1.5, eye_r * 0.7), "#FFD54F", 0.8)
        elif e == "smug" or e == "angry" or e == "determined":
            p = skia.Path()
            p.addOval(skia.Rect.MakeLTRB(x - eye_r * k, y - eye_r * 0.7, x + eye_r * k, y + eye_r))
            lid = skia.Path()
            lid.addRect(skia.Rect.MakeLTRB(x - eye_r * 2, y - eye_r * 2, x + eye_r * 2, y - eye_r * (0.05 if e != "determined" else 0.3)))
            half = skia.Op(p, lid, skia.PathOp.kDifference_PathOp) or skia.Path()
            pen.fill(half, ink, flat=True)
        else:
            wide = e in ("surprised", "scream", "shock")
            rx, ry = eye_r * k * (1.25 if wide else 1.0), eye_r * (1.25 if wide else 1.25 if cd["eyes"] != "dot" else 1.0)
            if wide:
                pen.fill(_oval(x, y, rx * 1.15, ry * 1.15), "#FFFFFF", flat=True)
                pen.line(_oval(x, y, rx * 1.15, ry * 1.15), ink, 1.3)
                pen.fill(_oval(x + lx * rx * 0.3, y + ly * ry * 0.3, rx * 0.45, ry * 0.45), ink, flat=True)
            else:
                pen.fill(_oval(x + lx * rx * 0.25, y + ly * ry * 0.2 + (eye_r * 0.35 if e == "shy" else 0), rx, ry), ink, flat=True)
                if cd["eyes"] in ("round", "big"):
                    pen.fill(_oval(x + lx * rx * 0.25 - rx * 0.35, y - ry * 0.38, rx * 0.36, ry * 0.32), "#FFFFFF", flat=True)
            if e == "sad":
                tear = _oval(x + rx * 0.6, y + ry * 1.6, rx * 0.35, ry * 0.5)
                pen.fill(tear, "#7FC8F8", 0.85, flat=True)
        # brows
        by = y - eye_r * (2.3 if e in ("surprised", "scream") else 1.9)
        tilt = {"angry": 0.55, "determined": 0.35, "sad": -0.45, "cry": -0.5, "shy": -0.25, "confused": 0.4 * s, "smug": 0.15}.get(e, 0.0)
        brow = skia.Path()
        if s > 0:
            x_in, x_out = x - eye_r * 1.05 * k, x + eye_r * 1.05 * k
            brow.moveTo(x_in, by + tilt * eye_r)
            brow.quadTo(x, by - eye_r * 0.25, x_out, by - tilt * eye_r * 0.3)
        else:
            x_in, x_out = x + eye_r * 1.05 * k, x - eye_r * 1.05 * k
            brow.moveTo(x_in, by + tilt * eye_r)
            brow.quadTo(x, by - eye_r * 0.25, x_out, by - tilt * eye_r * 0.3)
        if cd["body"] != "blob" or e in ("angry", "sad", "cry", "surprised", "determined", "confused"):
            pen.line(brow, shade(col["hair"], -0.1) if cd["hair"] != "none" else ink, 1.6)
    # glasses
    if cd["glasses"] != "none" and turn < 0.85:
        gr = eye_r * 2.0
        for s, k in sides:
            x = fx + s * ex * k * (1 - 0.3 * turn)
            if cd["glasses"] == "square":
                g = skia.Path()
                g.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x - gr * k, ey - gr * 0.8, x + gr * k, ey + gr * 0.8), 2, 2))
            else:
                g = _oval(x, ey, gr * k, gr * (0.95 if cd["glasses"] == "round" else 0.75))
            if cd["glasses"] == "sunglasses":
                pen.fill(g, "#1E1E24", 0.92, flat=True)
            else:
                pen.fill(g, "#FFFFFF", 0.22, flat=True)
            pen.line(g, ink, 1.6)
        br = skia.Path()
        br.moveTo(fx - ex * 0.45, ey - gr * 0.2)
        br.quadTo(fx, ey - gr * 0.45, fx + ex * 0.45, ey - gr * 0.2)
        pen.line(br, ink, 1.4)
    # cheeks
    if cd["blush"] or e in ("shy", "love"):
        a = 0.55 if e in ("shy", "love") else 0.35
        for s, k in sides:
            x = fx + s * ex * 1.25 * k
            pen.fill(_oval(x, ey + r * 0.3, r * 0.15 * k, r * 0.085), col["cheek"], a, flat=True)
    if cd["freckles"]:
        for s, k in sides:
            for i in range(3):
                pen.fill(_oval(fx + s * ex * (0.9 + 0.15 * i) * k, ey + r * 0.24 + (i % 2) * 1.2, 0.6, 0.6), shade(col["skin"], -0.3), flat=True)
    # muzzle (animals)
    if cd["body"] == "animal":
        pen.fill(_oval(fx, ey + r * 0.42, r * 0.32, r * 0.22), mix(col["skin"], "#FFFFFF", 0.55), flat=True)
        pen.fill(_oval(fx, ey + r * 0.3, r * 0.08, r * 0.055), ink, flat=True)
    # mouth
    my = ey + r * (0.5 if cd["body"] != "animal" else 0.52)
    mw = r * 0.22
    talk = pose.talk
    m = skia.Path()
    if e in ("scream", "surprised", "shock") or talk > 0.55:
        h = r * (0.32 if e == "scream" else 0.16 if e == "surprised" else 0.12 + 0.1 * talk)
        w = mw * (1.4 if e == "scream" else 0.8)
        mo = _oval(fx, my + h * 0.3, w, h)
        pen.fill(mo, "#7A2E3A", flat=True)
        if e == "scream":
            pen.fill(_oval(fx, my + h * 0.9, w * 0.6, h * 0.35), "#F06292", flat=True)
        pen.line(mo, ink, 1.5)
        return_restore(c)
        return
    if e in ("laugh", "excited", "happy") or talk > 0.15:
        open_h = r * (0.2 if e in ("laugh", "excited") else 0.12 if e == "happy" else 0.08 + 0.12 * talk)
        m.moveTo(fx - mw, my - open_h * 0.2)
        m.quadTo(fx, my - open_h * 0.35, fx + mw, my - open_h * 0.2)
        m.quadTo(fx, my + open_h * 1.6, fx - mw, my - open_h * 0.2)
        m.close()
        pen.fill(m, "#7A2E3A", flat=True)
        tongue = skia.Op(m, _oval(fx, my + open_h * 1.0, mw * 0.6, open_h * 0.55), skia.PathOp.kIntersect_PathOp) or skia.Path()
        pen.fill(tongue, "#F06292", flat=True)
        pen.line(m, ink, 1.5)
    elif e in ("sad", "cry"):
        m.moveTo(fx - mw * 0.9, my + r * 0.07)
        m.quadTo(fx, my - r * 0.1, fx + mw * 0.9, my + r * 0.07)
        pen.line(m, ink, 1.7)
    elif e == "angry":
        m.moveTo(fx - mw, my + r * 0.04)
        m.lineTo(fx - mw * 0.4, my)
        m.lineTo(fx, my + r * 0.04)
        m.lineTo(fx + mw * 0.4, my)
        m.lineTo(fx + mw, my + r * 0.04)
        pen.line(m, ink, 1.7)
    elif e == "confused":
        m.moveTo(fx - mw, my)
        m.cubicTo(fx - mw * 0.4, my - r * 0.08, fx + mw * 0.3, my + r * 0.08, fx + mw, my - r * 0.02)
        pen.line(m, ink, 1.7)
    elif e == "smug":
        m.moveTo(fx - mw * 0.8, my + r * 0.02)
        m.quadTo(fx + mw * 0.3, my + r * 0.07, fx + mw, my - r * 0.08)
        pen.line(m, ink, 1.7)
    elif e in ("sleepy", "neutral", "determined"):
        m.moveTo(fx - mw * 0.55, my + r * 0.02)
        m.quadTo(fx, my + r * (0.05 if e != "determined" else -0.02), fx + mw * 0.55, my + r * 0.02)
        pen.line(m, ink, 1.6)
    else:  # smile / shy / love
        w = mw * (0.6 if e == "shy" else 0.85)
        m.moveTo(fx - w, my - r * 0.02)
        m.quadTo(fx, my + r * 0.16, fx + w, my - r * 0.02)
        pen.line(m, ink, 1.7)
    if pose.tears or e == "cry":
        for s, k in sides:
            x = fx + s * ex * k
            tr = skia.Path()
            tr.moveTo(x, ey + eye_r * 0.6)
            tr.cubicTo(x + s * 2, ey + r * 0.5, x - s * 2, ey + r * 0.7 + 2 * math.sin(t * 8), x + s, ey + r * 0.95)
            pen.line(tr, "#7FC8F8", 2.4, 0.9)
    return_restore(c)


def return_restore(c: skia.Canvas) -> None:
    c.restore()


def _heart(x: float, y: float, s: float) -> skia.Path:
    p = skia.Path()
    p.moveTo(x, y + s * 0.85)
    p.cubicTo(x - s * 1.4, y - s * 0.1, x - s * 0.7, y - s * 1.1, x, y - s * 0.35)
    p.cubicTo(x + s * 0.7, y - s * 1.1, x + s * 1.4, y - s * 0.1, x, y + s * 0.85)
    p.close()
    return p


def _star(x: float, y: float, ro: float, ri: float, n: int = 5) -> skia.Path:
    p = skia.Path()
    for i in range(n * 2):
        a = -math.pi / 2 + i * math.pi / n
        rr = ro if i % 2 == 0 else ri
        (p.moveTo if i == 0 else p.lineTo)(x + math.cos(a) * rr, y + math.sin(a) * rr)
    p.close()
    return p


def _symbols(pen, cd: dict, hc, r: float, pose: Pose, expr: str, t: float, lw: float) -> None:
    cx, cy = hc
    sy = list(pose.symbols)
    if expr in ("surprised", "scream") and "!" not in sy:
        sy.append("!")
    if expr == "confused" and "?" not in sy:
        sy.append("?")
    if expr == "love" and "heart" not in sy:
        sy.append("heart")
    if expr == "angry" and "anger" not in sy:
        sy.append("anger")
    if expr in ("scream",) and "sweat" not in sy:
        sy.append("sweat")
    if expr == "sleepy" and "zzz" not in sy:
        sy.append("zzz")
    bob = math.sin(t * 5) * 2
    for s in sy:
        if s == "!":
            p = skia.Path()
            p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(cx + r * 1.15, cy - r * 1.55 + bob, cx + r * 1.32, cy - r * 0.95 + bob), 2, 2))
            pen.shape(p, "#FFD54F", lw * 0.6)
            pen.shape(_oval(cx + r * 1.235, cy - r * 0.78 + bob, r * 0.09, r * 0.09), "#FFD54F", lw * 0.6)
        elif s == "?":
            p = skia.Path()
            x0, y0 = cx + r * 1.2, cy - r * 1.35 + bob
            p.moveTo(x0 - r * 0.15, y0)
            p.cubicTo(x0 - r * 0.15, y0 - r * 0.35, x0 + r * 0.35, y0 - r * 0.35, x0 + r * 0.3, y0 - r * 0.05)
            p.cubicTo(x0 + r * 0.25, y0 + r * 0.15, x0, y0 + r * 0.1, x0, y0 + r * 0.35)
            pen.line(p, "#4A7BF7", 3.2)
            pen.fill(_oval(x0, y0 + r * 0.55, r * 0.07, r * 0.07), "#4A7BF7", flat=True)
        elif s == "heart":
            k = 1 + 0.12 * math.sin(t * 7)
            pen.shape(_heart(cx + r * 1.15, cy - r * 1.2 + bob, r * 0.28 * k), "#E5484D", lw * 0.6)
        elif s == "anger":
            p = skia.Path()
            x0, y0 = cx + r * 0.8, cy - r * 0.95
            for a in range(4):
                ang = a * math.pi / 2 + math.pi / 4
                p.moveTo(x0 + math.cos(ang) * r * 0.08, y0 + math.sin(ang) * r * 0.08)
                p.lineTo(x0 + math.cos(ang) * r * 0.25, y0 + math.sin(ang) * r * 0.25)
            pen.line(p, "#E5484D", 2.6)
        elif s == "sweat":
            p = skia.Path()
            x0, y0 = cx - r * 1.05, cy - r * 0.55 + abs(bob)
            p.moveTo(x0, y0 - r * 0.2)
            p.quadTo(x0 + r * 0.16, y0 + r * 0.05, x0, y0 + r * 0.12)
            p.quadTo(x0 - r * 0.16, y0 + r * 0.05, x0, y0 - r * 0.2)
            pen.shape(p, "#9ED8FF", lw * 0.5)
        elif s == "zzz":
            for i in range(3):
                zz = skia.Path()
                x0, y0, z = cx + r * (1.0 + 0.3 * i), cy - r * (1.0 + 0.35 * i) + bob, r * (0.12 + 0.04 * i)
                zz.moveTo(x0, y0)
                zz.lineTo(x0 + z, y0)
                zz.lineTo(x0, y0 + z)
                zz.lineTo(x0 + z, y0 + z)
                pen.line(zz, "#4A7BF7", 1.8)
        elif s == "sparkle":
            for i, (dx, dy) in enumerate(((1.2, -1.0), (-1.25, -0.8), (1.0, 0.4))):
                k = 0.6 + 0.4 * abs(math.sin(t * 4 + i))
                pen.shape(_star(cx + r * dx, cy + r * dy, r * 0.16 * k, r * 0.05 * k, 4), "#FFD54F", lw * 0.4)
