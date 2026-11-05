"""The voice catalog: every Edge TTS voice (free, online), with language, dialect and gender, so you can pick and preview one.
The list comes from Edge itself (cached); with no internet a small built-in list is used."""
from __future__ import annotations

import asyncio
import re
import time

from ..series import languages, media

SAMPLES = {
    "en": "Hello! This is how I will sound in your video.",
    "hi": "नमस्ते! आपके वीडियो में मेरी आवाज़ ऐसी सुनाई देगी।",
    "te": "నమస్కారం! మీ వీడియోలో నా గొంతు ఇలా ఉంటుంది.",
    "ta": "வணக்கம்! உங்கள் வீடியோவில் என் குரல் இப்படி இருக்கும்.",
    "kn": "ನಮಸ್ಕಾರ! ನಿಮ್ಮ ವೀಡಿಯೊದಲ್ಲಿ ನನ್ನ ಧ್ವನಿ ಹೀಗಿರುತ್ತದೆ.",
    "ml": "നമസ്കാരം! നിങ്ങളുടെ വീഡിയോയിൽ എന്റെ ശബ്ദം ഇങ്ങനെയായിരിക്കും.",
    "bn": "নমস্কার! আপনার ভিডিওতে আমার কণ্ঠ এমন শোনাবে।",
    "mr": "नमस्कार! तुमच्या व्हिडिओमध्ये माझा आवाज असा ऐकू येईल.",
    "gu": "નમસ્તે! તમારા વિડિઓમાં મારો અવાજ આવો સંભળાશે.",
    "es": "¡Hola! Así sonaré en tu vídeo.", "fr": "Bonjour ! Voici ma voix dans votre vidéo.",
    "de": "Hallo! So klinge ich in deinem Video.", "ja": "こんにちは！あなたの動画ではこんな声になります。",
    "zh": "你好！我在你的视频里的声音就是这样。", "ar": "مرحباً! هكذا سيكون صوتي في الفيديو الخاص بك.",
}
ID_RX = re.compile(r"^[A-Za-z]{2,3}-[A-Za-z0-9-]{2,40}$")
_cache: dict = {"t": 0.0, "voices": []}


def valid_id(v: str | None) -> bool:
    return bool(v) and bool(ID_RX.match(str(v)))


def _fallback() -> list[dict]:
    out = []
    for lg in languages.LANGS.values():
        for gender, pool in (("Male", lg.edge_male), ("Female", lg.edge_female)):
            for v in pool:
                loc = "-".join(v.split("-")[:2])
                out.append({"id": v, "name": v.split("-")[-1].replace("Neural", ""), "locale": loc, "language": lg.name, "dialect": loc.split("-")[-1],
                            "gender": gender, "tags": []})
    return out


def _parse(raw: dict) -> dict:
    fn = raw.get("FriendlyName") or ""
    m = re.search(r"-\s*([^()]+?)\s*\(([^)]+)\)\s*$", fn)
    loc = raw.get("Locale") or ""
    tags = [*(raw.get("VoiceTag", {}).get("VoicePersonalities") or []), *(raw.get("VoiceTag", {}).get("ContentCategories") or [])]
    return {"id": raw["ShortName"], "name": raw["ShortName"].split("-")[-1].replace("Neural", ""), "locale": loc,
            "language": m.group(1) if m else loc.split("-")[0], "dialect": m.group(2) if m else loc.split("-")[-1],
            "gender": raw.get("Gender") or "", "tags": tags[:3]}


def catalog() -> list[dict]:
    if _cache["voices"] and time.time() - _cache["t"] < 3600:
        return _cache["voices"]
    try:
        import edge_tts  # type: ignore
        raw = asyncio.run(edge_tts.list_voices())
        voices = sorted((_parse(r) for r in raw), key=lambda v: (v["language"], v["dialect"], v["name"]))
    except Exception:  # noqa: BLE001 - offline or edge-tts missing
        voices = _fallback()
    _cache.update(t=time.time(), voices=voices)
    return voices


def search(language: str = "", gender: str = "") -> list[dict]:
    """Filter by language (its name, like "Hindi", or its code, like "hi") and gender."""
    lg = language.strip().lower()
    return [v for v in catalog() if (not lg or v["language"].lower() == lg or v["locale"].lower().startswith(lg + "-"))
            and (not gender or v["gender"].lower() == gender.strip().lower())]


def preview(voice: str, text: str | None = None) -> bytes:
    base = voice.split("-")[0].lower()
    return media.edge_say((text or SAMPLES.get(base) or SAMPLES["en"])[:200], {"edge": voice, "pitch": "+0Hz"}, "neutral")
