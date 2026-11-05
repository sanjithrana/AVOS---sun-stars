"""Test double: a stand-in for Ollama (same HTTP API) that answers the studio's crew prompts with realistic JSON.
Every 4th JSON request first returns chatter (not JSON) to exercise the retry path."""
import asyncio
import itertools
import json
import os
import re
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
COUNT = itertools.count()
CALLS: list[dict] = []      # every /api/chat request: {model, images, broken, system, prompt}
LOG = open(os.environ.get("FAKE_OLLAMA_LOG") or os.path.join(tempfile.gettempdir(), "fake_ollama.log"), "a")
MODELS = [{"name": "qwen2.5:7b", "model": "qwen2.5:7b", "size": 4_700_000_000}, {"name": "qwen2.5vl:7b", "model": "qwen2.5vl:7b", "size": 6_000_000_000}]


@app.get("/api/tags")
async def tags():
    return {"models": MODELS}


@app.post("/api/pull")
async def pull(req: Request):
    body = await req.json()
    name = body.get("name") or body.get("model")

    async def gen():
        for i in range(0, 101, 25):
            yield json.dumps({"status": "pulling", "total": 100, "completed": i}) + "\n"
            await asyncio.sleep(0.3)
        MODELS.append({"name": name, "model": name})
        yield json.dumps({"status": "success"}) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


def series_answer(system: str, prompt: str) -> dict | None:
    """Answers for the Series writers' room (studio/series/writers.py)."""
    if "[avos-design-dna]" in system:
        return {"name": "Tiny Flat Comedy", "medium": "flat 2D TV cartoon", "line": "thick dark brown outlines", "shading": "flat cel, one shadow tone",
                "proportions": "big round heads, kids 3 heads tall", "texture": "clean digital", "palette": ["#2B2D42", "#FFD166", "#EF476F", "nope"],
                "lighting": "bright and even", "camera": {"default_lens": 35, "angle": "eye level", "max_speed": "slow",
                                                         "allowed_moves": ["static", "push_in", "pan_left", "pan_right"]},
                "motion": {"pacing": "snappy", "ease": "power2.out", "squash_stretch": True, "holds": True, "feel": "rubbery and bouncy"},
                "sound": {"ambience": "busy Indian neighbourhood", "music": "playful tabla and ukulele", "sfx_style": "cartoon, exaggerated"},
                "avoid": ["photorealism", "3D render look"]}
    if "[avos-series-bible]" in system:
        return {"logline": "A noisy family in a tiny Pune flat turns every small problem into a war.", "world": "Pune, 2026",
                "style_prompt": "flat 2D cartoon, thick outlines, warm colours",
                "characters": [{"name": "Bunty", "role": "lead", "age": "12", "gender": "male", "personality": "schemer with a big heart",
                                "look": "skinny boy, messy black hair, big eyes", "outfit": "green t-shirt with a yellow stripe, blue shorts",
                                "voice": "young boy, quick, cheeky", "catchphrase": "Plan ready hai!"},
                               {"name": "Mummy", "role": "supporting", "age": "40", "gender": "female", "personality": "strict, loving, sees everything",
                                "look": "round face, hair in a bun, round glasses", "outfit": "purple saree with a red border",
                                "voice": "warm adult woman, firm", "catchphrase": ""}],
                "locations": [{"name": "Living room", "description": "small living room, old TV, a sofa with a flowered cover"},
                              {"name": "Kitchen", "description": "narrow kitchen, steel utensils, pressure cooker"}]}
    if "[avos-head-writer]" in system:
        n = len(re.findall(r"\d+(?:\.\d+)?", re.search(r"Parts \(minutes each\): \[([^\]]*)\]", prompt).group(1)))
        return {"title": "The Remote War", "logline": "Bunty breaks the remote before the final.",
                "parts": [{"index": i + 1, "summary": f"Part {i + 1}: the remote crisis grows", "beats": ["a lie", "a chase"],
                           "ends_with": "Mummy finds a clue"} for i in range(n)]}
    if "[avos-scriptwriter]" in system:
        ids = re.findall(r'"id": "([a-z0-9-]+)", "name"', prompt.split("Approved characters:")[1].split("\n")[0])
        loc = (re.findall(r'"id": "([a-z0-9-]+)"', prompt.split("Locations:")[1].split("\n")[0]) or ["home"])[0]
        a, b = (ids + ids)[:2]
        return {"scenes": [{"location": loc, "time": "evening", "characters": [a, b], "beats": [
            {"type": "action", "text": "The TV remote lies in two pieces on the floor", "characters": [a], "sfx": "plastic clatters", "seconds": 3},
            {"type": "line", "character": a, "text": "मम्मी, मैंने कुछ नहीं किया!", "emotion": "scared", "action": "hides the pieces"},
            {"type": "line", "character": b, "text": "तो ये रिमोट खुद टूट गया?", "emotion": "sarcastic", "action": "crosses her arms"},
            {"type": "line", "character": a, "text": "हाँ! शायद गर्मी से!", "emotion": "excited", "action": "grins"}]}]}
    if "[avos-scene-director]" in system:
        rows = [json.loads(line) for line in prompt.split("beat by beat (seconds = how long the shot lasts):\n")[1].split("\n\nAnswer")[0].splitlines()]
        out = []
        for i, r in enumerate(rows):
            who = r.get("speaker") or (r.get("characters") or [None])[0]
            shot = {"beat": r["beat"], "framing": ["wide", "close-up", "medium", "two-shot"][i % 4],
                    "camera": {"move": ["static", "push_in", "pan_right", "orbit_left"][i % 4], "ease": "power2.out"},
                    "picture": f"shot {i + 1}"}
            if who:
                shot["actors"] = [{"id": who, "x": -0.4, "z": 0.2, "facing": "camera", "pose": "leaning forward", "expression": "wide-eyed"}]
                shot["tracks"] = [{"target": who, "keys": [{"t": 0, "action": "freezes"}, {"t": 1.0, "action": "steps back", "x": -0.8}]}]
                shot["props"] = [{"name": "TV remote", "x": 0.3, "z": 0.5, "held_by": who}]
            out.append(shot)
        return {"shots": out}
    if "[avos-sound-designer]" in system:
        return {"ambience": {"s1": "evening living room: ceiling fan, distant traffic, a TV next door"},
                "sfx": {"s1b1": "plastic remote clatters on tiles, a guilty gulp"}, "music": "sneaky pizzicato and tabla, building to a sting"}
    if "[avos-shot-qa]" in system:
        return {"character": {"ok": True, "why": ""}, "style": {"ok": True, "why": ""}, "artifacts": {"ok": True, "why": ""}, "fix": ""}
    if "[avos-continuity]" in system:
        return {"summary": "Bunty broke the remote and blamed the heat; Mummy didn't believe him.", "facts": ["the TV remote is broken"]}
    return None


def answer(system: str, prompt: str, images: int) -> dict:
    p = system + "\n" + prompt
    sa = series_answer(system, prompt)
    if sa is not None:
        return sa
    if "Break down this reference video" in p:
        m = re.search(r'The rule-based pick is "([^"]+)"', p)
        return {"thinking": "Flat pastel frames, thick outlines, quick cuts on the beat; it reads as a chibi comic.",
                "medium": "2d-vector", "style": m.group(1) if m else "narrated-comic-vlog", "confidence": 0.78,
                "why": ["flat colours and bold outlines", "one idea per shot, 2-3 s each", "captions carry the jokes"],
                "palette": ["#2B2D42", "#FFD166", "#EF476F", "#06D6A0", "#F8F9FA"], "color_arc": "night blues warming to gold at the end",
                "character_language": "round chibi heads, stubby limbs", "editing": "hard cuts on the beat, a few whip transitions",
                "structure": "setup, three tries, payoff that echoes the opening", "text_use": "big captions for punchlines",
                "keys": ["each shot lands one joke", "camera always moving", "ending mirrors the opening"]}
    if "Write the pre-production plan" in p:
        ids = re.findall(r'"id": "(S\d+)"', p)
        beats = [("Luna stares at the full moon from her window", "bedroom", "night", "think", "dreamy", ["moon", "window"], "Every night, the same wish…", "fade"),
                 ("She builds a wobbly tower of boxes in the garden", "park", "night", "walk", "determined", ["moon"], "", "wipe"),
                 ("Climbs to the top, reaches up — still far away", "park", "night", "point", "determined", ["moon", "star"], "Almost…", "cut"),
                 ("The tower collapses, she tumbles into the grass", "park", "night", "fall", "surprised", ["moon"], "Oops!", "whip"),
                 ("Her cat Pip pushes a bucket of water to her", "park", "night", "talk", "happy", ["moon"], "", "cut"),
                 ("The moon's reflection in the bucket — she touches it", "park", "night", "cheer", "excited", ["moon", "star"], "Got it!", "dissolve"),
                 ("Back at the window, both wave goodnight to the moon", "bedroom", "night", "wave", "happy", ["moon", "window"], "Goodnight, moon.", "fade")]
        shots = []
        for i, sid in enumerate(ids):
            b = beats[min(i, len(beats) - 1)]
            actors = [{"id": "luna", "action": b[3], "expression": b[4]}]
            if i >= max(1, len(ids) - 2):     # the cat joins for the last two shots
                actors.append({"id": "pip", "action": "cheer" if i == len(ids) - 2 else "idle", "expression": "happy"})
            shots.append({"id": sid, "summary": b[0], "action": b[0], "setting": b[1], "time": b[2], "actors": actors, "props": b[5],
                          "fx": ["sparkles"] if b[3] == "cheer" else [], "text": b[6], "narration": "", "transition_in": b[7],
                          "reads": [b[0]]})
        return {"thinking": "Use the reference's three-tries structure: wish, try, fail, clever win, echo.",
                "title": "Luna and the Moon", "logline": "A girl who wants to touch the moon finds a clever way with her cat's help.",
                "motif": "the round moon framed by her window", "look": {"palette": ["#1B1F3B", "#FFF3C4", "#FFB347", "#7EC8E3", "#E86A92"],
                                                                         "color_arc": "deep blue night → warm gold glow at the payoff", "typography": "rounded bold"},
                "borrowed_from_reference": ["one idea per shot", "fall gag on the beat", "ending mirrors the opening"],
                "characters": [{"id": "luna", "name": "Luna", "design": "a small girl, long black hair with a yellow bow, yellow raincoat, blue boots",
                                "arc": "wishes → tries → wins with help"},
                               {"id": "pip", "name": "Pip", "design": "a round orange cat with a white belly", "arc": "sleepy → helpful"}],
                "shots": shots, "required_inputs": [], "open_questions": ["Should Luna's cat talk, or just meow?"]}
    if "You design one character" in p:
        if '"id": "pip"' in p:
            return {"body": "animal", "height": 0.7, "build": "round", "colors": {"skin": "#F4A259", "hair": "#C96E2E", "top": "#FFFFFF", "bottom": "#FFFFFF",
                    "shoes": "#C96E2E", "accent": "#FFFFFF"}, "hair": "none", "eyes": "big", "glasses": "none", "ears": "cat", "tail": "cat",
                    "top": "none", "bottom": "none", "accessories": [], "blush": True, "freckles": False}
        return {"body": "chibi", "height": 0.95, "build": "normal", "colors": {"skin": "#FFD9B8", "hair": "#1E1E2A", "top": "#FFC93C", "bottom": "#3F6FD8",
                "shoes": "#3F6FD8", "accent": "#FFE066"}, "hair": "long", "eyes": "big", "glasses": "none", "ears": "none", "tail": "none",
                "top": "hoodie", "bottom": "pants", "accessories": ["bow"], "blush": True, "freckles": False}
    if "You are a shot builder" in p:
        out = {}
        for sid in re.findall(r'"id": "(S\d+)"', p.split("Engine drafts")[0]):
            out[sid] = {"camera": {"move": "dolly_in", "pace": "slow", "from": {"fill": 0.5}, "to": {"fill": 0.62}}}
        return {"thinking": "Keep the drafts, slow push-ins to match the reference.", "shots": out}
    if "independent reviewer" in system or "independent shot reviewer" in system:
        return {"thinking": "Limbs attached, faces readable.", "issues": []}
    if "final critic" in system:
        return {"thinking": "Seams are smooth.", "summary": "Pacing follows the reference and the ending mirrors the opening. The fall gag lands.",
                "nice_to_have": ["a little more squash on the landing"]}
    if "The user commented on the plan" in p:
        user = re.search(r"User: (.*)", p).group(1)
        r = {"thinking": "Apply the note.", "reply": [f"Done: {user[:80]}"]}
        if "title" in user.lower():
            r["title"] = "Moon Catcher"
        if re.search(r"S3", user):
            r["shots"] = [{"id": "S3", "seconds": 3.5, "summary": "She stretches on tiptoe, the moon just out of reach", "text": "So close!"}]
        return r
    if "Map each note" in p:
        return {"map": [{"note": 0, "shots": ["S2"]}]}
    if "revising one shot" in system or "builder of this shot" in system:
        m = re.search(r"Spec: (\{.*\})\n", p) or re.search(r"spec: (\{.*\})\n", p)
        spec = json.loads(m.group(1)) if m else {}
        for a in spec.get("actors") or []:
            a["scale"] = min(0.8, float(a.get("scale", 0.5)) * 1.25)
        return {"thinking": "Make the character bigger as asked.", "spec": spec, "changes": ["characters 25% bigger"], "cannot": []}
    if "fix a 2D character rig" in system:
        return {"thinking": "Darken the outfit.", "changes": {"colors": {"top": "#E09F1F"}}, "cannot": []}
    return {"thinking": "ok"}


@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    n = next(COUNT)
    msgs = body.get("messages") or []
    system = next((m["content"] for m in msgs if m["role"] == "system"), "")
    last = msgs[-1]
    prompt = last["content"] if isinstance(last["content"], str) else str(last["content"])
    images = len(last.get("images") or [])
    if body.get("model") not in [m["name"] for m in MODELS]:
        return JSONResponse({"error": f"model '{body.get('model')}' not found"}, status_code=404)
    data = answer(system, prompt, images)
    text = json.dumps(data, ensure_ascii=False)
    if n % 4 == 3 and "Your last reply was not valid JSON" not in prompt:
        text = "Sure! Here is my plan: the story will be about..."   # broken reply → the studio retries
    CALLS.append({"model": body.get("model"), "images": images, "broken": text.startswith("Sure!"), "system": system[:200], "prompt": prompt[:400]})
    LOG.write(json.dumps({"n": n, "model": body.get("model"), "images": images, "prompt": prompt[:160], "reply": text[:160]}) + "\n")
    LOG.flush()

    async def gen():
        for i in range(0, len(text), 40):
            yield json.dumps({"message": {"role": "assistant", "content": text[i:i + 40]}, "done": False}) + "\n"
            await asyncio.sleep(0.005)
        yield json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=11434, log_level="warning")
