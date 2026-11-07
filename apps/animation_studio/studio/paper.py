"""The paper-cut look, in one place, for every skill that can use it (Explainer, Stickman, Company Story, Skill Lab).

It is the handcrafted editorial stop-motion workflow written as code instead of a chat wizard: the app already has steps
(research → script → pictures → motion → voice), so what the workflow actually adds is the CRAFT RULES at each step:

    narration_rules(seconds)  one sentence = one visual, a retention beat every 4-6 sentences, alternating rhythm, no filler
    ART                       hero rule, fresh background per scene, negative space, palette by subject, museum lighting
    picture(subject, topic)   a self-contained image prompt: subject, action, environment, depth, construction, light, palette
    TAIL                      the paper-construction sentence every image prompt ends with
    NEGATIVE                  what the look must never become (cartoon, clip art, flat vector, digital painting, photo)
    animation(seconds)        the universal image-to-video prompt: locked camera, layer-by-layer assembly, then living poster

Everything is original wording about materials and craft; no existing film, script or creator is imitated.
"""
from __future__ import annotations

import re
from itertools import pairwise

ID = "paper"
NAME = "Paper-cut"
MARK = "handcrafted paper sculpture"          # how other modules recognise the look in a free-text style field

# LOOK_SHORT goes first in a picture prompt and must survive the free picture services, which cut long prompts
# (Pollinations at about 900 characters); LOOK is the full description, for places with room for it.
LOOK_SHORT = ("a handcrafted PAPER-CUT diorama: every object cut from layered cardstock and kraft paper with exposed edges, visible paper fibres, real "
              "paper thickness and deep shadows between the layers, like premium editorial stop-motion on a tabletop")
LOOK = (LOOK_SHORT + ", stacked contours and recessed layers, handcrafted glue seams, museum-quality craftsmanship, a premium handcrafted paper "
        "sculpture photographed with cinematic lighting")

TAIL = ("Every visible object is handcrafted entirely from individually cut cardstock, handmade paper, watercolour paper, kraft paper and corrugated "
        "paper layers, with exposed paper edges, stacked contours, visible paper fibres, recessed layers, handcrafted glue seams, realistic paper "
        "thickness, dramatic shadow separation, museum-quality craftsmanship, luxurious editorial stop-motion aesthetic, premium handcrafted paper "
        "sculpture, cinematic lighting, generous negative space, ultra detailed, 8K, no text, no logos, no watermark.")

LIGHTING = ("Soft museum lighting with a top-left directional key light, warm bounce fill from the right, deep paper shadows under every layer, and the "
            "thickness of each sheet clearly visible along its cut edge.")

NEGATIVE = ("cartoon, clip art, children's book illustration, flat vector, digital painting, low-detail illustration, smooth plastic 3D render, CGI, "
            "photograph, photorealistic skin, text, letters, numbers, captions, logos, labels, watermark, cluttered frame, muddy shadows")

HERO = "Exactly ONE hero subject per picture, at most three supporting objects, and everything else removed."
SPACE = "Generous negative space around the hero; editorial clarity comes before decoration."
FRESH = "Every scene gets its own environment; no background is ever reused inside one video."

# A palette that fits the subject, never forced onto it.
PALETTES = {
    "history": "warm earth tones: ochre, umber, faded terracotta and bone",
    "nature": "organic greens: moss, sage, deep forest and warm bark brown",
    "technology": "cool blue and silver: slate, steel, pale cyan and graphite",
    "luxury": "gold and ivory: champagne, warm brass, cream and soft shadow brown",
    "space": "deep indigo: midnight blue, violet shadow, cold starlight white and a single warm accent",
    "business": "a neutral corporate palette: paper white, soft grey-blue, warm sand and one confident accent",
    "science": "clean cool neutrals: chalk white, pale teal, mid grey and one bright signal colour",
    "sport": "bold saturated contrast: deep court green or track red against chalk white and charcoal",
    "food": "warm appetising tones: cream, toasted wheat, tomato red and herb green",
    "ocean": "layered blues: pale foam, turquoise, deep navy and wet sand",
}
_TOPIC = [
    ("history", r"histor|ancient|empire|war|king|queen|dynasty|century|medieval|revolution|civilis|civiliz"),
    ("space", r"space|planet|galaxy|star|cosmic|black hole|orbit|rocket|astronaut|moon|mars|universe"),
    ("nature", r"nature|animal|forest|wildlife|bird|tree|jungle|insect|shark|whale|plant|ecosystem"),
    ("ocean", r"ocean|sea|reef|deep sea|marine|tide|coral"),
    ("technology", r"tech|computer|ai\b|artificial intelligence|robot|software|internet|chip|phone|machine learning|code|data"),
    ("science", r"science|physic|chemi|biolog|cell|virus|atom|energy|experiment|dna|brain|math"),
    ("business", r"business|compan|startup|founder|market|revenue|industry|brand|factory|profit|economy|bank"),
    ("luxury", r"luxur|jewel|gold|diamond|watch|fashion|perfume|couture"),
    ("sport", r"sport|football|cricket|tennis|olympic|athlete|race|match|basketball"),
    ("food", r"food|recipe|kitchen|coffee|chocolate|restaurant|spice|bread|farm"),
]


def palette_for(topic: str | None) -> str:
    """The palette that fits the subject (never forced): matched on the topic's own words."""
    t = (topic or "").lower()
    for key, rx in _TOPIC:
        if re.search(rx, t):
            return PALETTES[key]
    return PALETTES["business"] if t else "a restrained palette of three or four colours drawn from the subject itself"


def is_paper(style: str | None) -> bool:
    """True when a project's free-text style field asks for this look."""
    s = (style or "").lower()
    return MARK in s or "paper-cut" in s or "paper cut" in s or "papercut" in s


TAIL_SHORT = ("Exposed paper edges, stacked paper layers and real paper thickness throughout, deep shadow separation, generous negative space, "
              "no text, no logos, no watermark.")


def tail(topic: str | None = None, short: bool = False) -> str:
    """What every paper image prompt ends with: palette, light, craft and the hard rules. `short` for prompts that are already
    long, so the free picture services do not cut the rules off the end."""
    if short:
        return f"Palette: {palette_for(topic)}. {LIGHTING} {TAIL_SHORT}"
    return f"Colour palette: {palette_for(topic)}. {LIGHTING} {HERO} {SPACE} {TAIL}"


def picture(subject: str, topic: str | None = None, environment: str = "", composition: str = "") -> str:
    """One self-contained image prompt. Never relies on an earlier prompt: subject and action first (picture models weigh the
    opening words most), then environment and depth, then construction, light and palette."""
    bits = [f"{LOOK_SHORT}.", subject.strip().rstrip(".") + "."]
    if environment:
        bits.append(f"Environment: {environment.rstrip('.')}.")
    if composition:
        bits.append(f"Composition: {composition.rstrip('.')}.")
    bits.append("Clear depth in three planes: a foreground paper layer close to the lens, the hero subject in the midground, and simple cut-paper shapes "
                "far behind, each plane casting its own shadow onto the one below.")
    bits.append(tail(topic))
    return " ".join(bits)


# ---------- motion ----------
_ASSEMBLY = ("The illustration assembles itself from back to front like a handcrafted paper sculpture being built on a table: background sheet, sky, "
             "light sources, clouds, distant scenery, architecture, ground, landscape details, vegetation, large objects, secondary objects, foreground "
             "objects, then the characters and their clothing and accessories. Each layer slides or drops gently into its final place, settles with a tiny "
             "paper bounce and casts a real layered shadow. Nothing moves again once it has landed, and every element keeps the exact position, size and "
             "perspective it has in the picture.")
_LIVING = ("The artwork becomes a living paper poster: everything stays exactly where it is and only tiny handcrafted movement is allowed. Characters "
           "blink slowly, breathe, shift the head a little and adjust a hand. Clouds drift, leaves and grass sway, water ripples, smoke curls, flags and "
           "fabric flutter, and the key light shifts slowly across the paper layers so the shadows breathe. Nothing changes place, nothing scales, nothing "
           "rotates noticeably, and nothing enters or leaves the frame.")
_CRAFT = ("Movement must feel handcrafted: a tiny stop-motion jitter, natural paper friction, a slight settle after each placement, the weight of real "
          "cardstock, soft paper collisions and visible layered depth throughout. Avoid perfectly smooth CGI motion.")
_CAMERA = ("The camera is completely locked for the whole clip: no zoom, pan, tilt, rotation, orbit, dolly, tracking, crane, handheld sway, shake, focus "
           "pull or lens change, and no cuts, transitions, scene changes, morphing, object replacement or time skips. One continuous static shot.")
_SOUND = ("Sound: no music, no narration and no voices, only close handcrafted paper ASMR that suits the scene, such as paper sliding, cardboard friction, "
          "soft paper taps, stacking, light knocks and gentle rustling, with quiet matching ambience.")


def animation(seconds: float = 10.0, assemble: bool = True, audio: bool = False, locked: bool = True) -> str:
    """The universal image-to-video prompt for a paper picture. With `assemble` (clips of about 7 seconds or more) the scene
    builds itself layer by layer and then lives; shorter clips skip straight to the living poster. `locked` off where the studio
    writes its own camera move for the clip, so the two instructions never contradict each other."""
    s = max(2.0, float(seconds))
    use = assemble and s >= 6.5
    head = (f"Animate the attached image as a {round(s)}-second premium handcrafted stop-motion editorial paper-cut shot. Keep the composition exactly as "
            "it is: do not redesign, reposition, recolour or replace anything, and keep every element's original size, place, perspective and layering. "
            "The whole scene stays built from thick layered cardstock with visible stacked edges, paper fibres, die-cut shapes, embossed texture, deep "
            "dimensional shadows and honest tabletop imperfections.")
    body = [_CAMERA] if locked else ["The camera move stays slow and simple, and nothing cuts, morphs or is replaced inside the shot."]
    if use:
        cut = round(s * 0.7, 1)
        body += [f"0-{cut}s - LAYER-BY-LAYER ASSEMBLY. {_ASSEMBLY} The picture is fully assembled by about {cut} seconds.",
                 f"{cut}-{round(s, 1)}s - LIVING PAPER POSTER. {_LIVING}"]
    else:
        body += [f"The whole {round(s)} seconds is a living paper poster. {_LIVING}"]
    body += [_CRAFT, _SOUND if not audio else _SOUND.replace("no music, no narration and no voices, only", "keep the narration audible over")]
    body += ["The finished clip should feel like a real handcrafted paper sculpture on a tabletop, filmed in one locked shot."]
    return head + " " + " ".join(body)


# ---------- writing ----------
# Sentences for a finished video of this length. One sentence = one shot = one visual idea, which works out at a little over two
# seconds a sentence: the fast documentary cut this look is made for. It means a one-minute video is 22-30 pictures and clips,
# not the dozen a slower look would use, so it takes longer to render and costs more at the video model.
PACE = [(30, 12, 16), (60, 22, 30), (120, 45, 60), (180, 70, 90), (300, 120, 150)]
MIN_SHOT = 2.0                                      # the shortest shot the studio will cut (explainer/spec.py)

RETENTION = ("surprising fact", "visual reveal", "historical twist", "unanswered question", "contrast", "unexpected comparison", "scale reveal",
             "consequence", "mystery", "payoff")


def sentences_for(seconds: float, cap: int = 0) -> tuple[int, int]:
    """How many narration sentences a video of this length needs (interpolated between the pacing marks). Never more than the
    video has room for at the shortest cuttable shot; `cap` lowers it further when a studio wants fewer, longer shots."""
    s = max(5.0, float(seconds))
    if s <= PACE[0][0]:
        f = s / PACE[0][0]
        lo, hi = max(3, round(PACE[0][1] * f)), max(4, round(PACE[0][2] * f))
    else:
        lo = hi = 0
        for (a, alo, ahi), (b, blo, bhi) in pairwise(PACE):
            if s <= b:
                f = (s - a) / (b - a)
                lo, hi = round(alo + (blo - alo) * f), round(ahi + (bhi - ahi) * f)
                break
        if not hi:
            f = s / PACE[-1][0]
            lo, hi = round(PACE[-1][1] * f), round(PACE[-1][2] * f)
    room = int(s // MIN_SHOT)
    top = min(hi, room, cap or hi)
    return max(2, min(lo, top)), max(2, top)


def narration_rules(seconds: float, cap: int = 0) -> str:
    """The writing rules that make a paper-cut video work: one sentence, one visual."""
    lo, hi = sentences_for(seconds, cap)
    each = round(float(seconds) / max(1, hi), 1)
    return (f"NARRATION FOR THE PAPER-CUT LOOK: write {lo}-{hi} sentences for these {round(float(seconds))} seconds, because each sentence becomes ONE "
            f"picture and is on screen for only about {each} seconds, so keep the sentences short. Every sentence must carry exactly one complete visual "
            "idea; never put two ideas in "
            "one sentence, because the second one cannot be shown. Write in a documentary voice: cinematic, curiosity-driven, easy to understand, active "
            f"voice, no filler and no repetition. Every four to six sentences, land one of these: {', '.join(RETENTION)}. Never give two sentences in a row "
            "the same rhythm; alternate short and medium so the narration breathes. No greetings, no introductions of yourself, no outros, no subscribe or "
            "sponsor lines, and no numbering inside the narration. ")


ART = ("PAPER-CUT ART DIRECTION. Before describing each picture, decide the single most important visual idea of the sentence, what deserves hero focus "
       f"and what can be removed, then design only around that. {HERO} {FRESH} {SPACE} Choose a colour palette that naturally fits the subject and never "
       "force colours onto it. Light every scene as a museum exhibit: a top-left key light, warm bounce, deep paper shadows and visible paper thickness. "
       "Each picture description must stand on its own and name the subject, its action, the environment, the composition, the depth from foreground to "
       "background, how the paper is constructed, the lighting, the palette and the mood. Every frame should look like a premium museum exhibit, a luxury "
       "editorial illustration, a high-end paper sculpture or an award-winning stop-motion film, and never like a cartoon, clip art, a children's book, a "
       "flat vector, a digital painting or a low-detail illustration. Everything must be original: use publicly known facts expressed in your own words and "
       "your own visual metaphors, never another creator's wording, structure or scenes. ")


def rules(seconds: float) -> str:
    """Everything a script writer needs for this look, in one block."""
    return narration_rules(seconds) + ART


def for_writer(md: str, seconds: float) -> str:
    """The script writer's share of apps/skills/avos-paper-art/SKILL.md: the craft rules, without the quoted prompt blocks and
    the motion section (code already applies those, word for word, to every picture and clip). Falls back to the built-in rules
    when the file is missing, and stays short enough for a small AI crew's per-minute token limit."""
    body = (md or "").strip()
    if not body:
        return rules(seconds)
    out, skip = [], False
    for line in body.splitlines():
        if line.startswith("## "):
            skip = bool(re.search(r"motion|where this is used", line, re.IGNORECASE))
        if skip or line.lstrip().startswith(">"):
            continue
        out.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    if len(text) > 4500:                                      # whole lines only, so a rule is never cut in half
        kept: list[str] = []
        for line in text.splitlines():
            if sum(len(x) + 1 for x in kept) + len(line) > 4500:
                break
            kept.append(line)
        text = "\n".join(kept).strip()
    return (text + "\n") if text else rules(seconds)
