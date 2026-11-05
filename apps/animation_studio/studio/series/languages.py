"""Languages a Series can speak, and which voice engines handle each one.

    voice design (a new voice per character, from a description):  Indic Parler-TTS (21 languages) → Edge voice
    every line (cloned from the approved sample):                   Chatterbox (23) → IndicF5 (11 Indian) → Edge voice

Edge voices (Microsoft, free, need internet) are the no-GPU fallback; each character gets its own Edge voice with a
pitch / speed offset so two characters never sound the same.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Lang:
    code: str                 # what the series stores (BCP-47-ish)
    name: str
    tts: str                  # the code the voice models take
    script: str               # how dialogue is written
    edge_male: tuple[str, ...]
    edge_female: tuple[str, ...]
    edge_child: tuple[str, ...] = field(default_factory=tuple)
    note: str = ""


L = Lang
LANGS: dict[str, Lang] = {x.code: x for x in [
    L("hi", "Hindi", "hi", "Devanagari", ("hi-IN-MadhurNeural",), ("hi-IN-SwaraNeural",)),
    L("hinglish", "Hinglish (Hindi + English, as people talk)", "hi", "Devanagari, English words written as they sound in Devanagari",
      ("hi-IN-MadhurNeural",), ("hi-IN-SwaraNeural",), note="Spoken by the Hindi voices."),
    L("en-IN", "English (India)", "en", "Latin", ("en-IN-PrabhatNeural",), ("en-IN-NeerjaNeural",)),
    L("en", "English (US)", "en", "Latin", ("en-US-GuyNeural", "en-US-AndrewNeural"), ("en-US-JennyNeural", "en-US-AriaNeural"),
      ("en-US-AnaNeural",)),
    L("en-GB", "English (UK)", "en", "Latin", ("en-GB-RyanNeural",), ("en-GB-SoniaNeural",)),
    L("ta", "Tamil", "ta", "Tamil", ("ta-IN-ValluvarNeural",), ("ta-IN-PallaviNeural",)),
    L("te", "Telugu", "te", "Telugu", ("te-IN-MohanNeural",), ("te-IN-ShrutiNeural",)),
    L("bn", "Bengali", "bn", "Bengali", ("bn-IN-BashkarNeural",), ("bn-IN-TanishaaNeural",)),
    L("mr", "Marathi", "mr", "Devanagari", ("mr-IN-ManoharNeural",), ("mr-IN-AarohiNeural",)),
    L("gu", "Gujarati", "gu", "Gujarati", ("gu-IN-NiranjanNeural",), ("gu-IN-DhwaniNeural",)),
    L("kn", "Kannada", "kn", "Kannada", ("kn-IN-GaganNeural",), ("kn-IN-SapnaNeural",)),
    L("ml", "Malayalam", "ml", "Malayalam", ("ml-IN-MidhunNeural",), ("ml-IN-SobhanaNeural",)),
    L("pa", "Punjabi", "pa", "Gurmukhi", ("hi-IN-MadhurNeural",), ("hi-IN-SwaraNeural",),
      note="No Punjabi Edge voice: without a GPU voice the Hindi voices read it."),
    L("ur", "Urdu", "ur", "Urdu (Nastaliq)", ("ur-PK-AsadNeural",), ("ur-PK-UzmaNeural",)),
    L("es", "Spanish", "es", "Latin", ("es-ES-AlvaroNeural", "es-MX-JorgeNeural"), ("es-ES-ElviraNeural", "es-MX-DaliaNeural")),
    L("fr", "French", "fr", "Latin", ("fr-FR-HenriNeural",), ("fr-FR-DeniseNeural",)),
    L("de", "German", "de", "Latin", ("de-DE-ConradNeural",), ("de-DE-KatjaNeural",)),
    L("pt", "Portuguese", "pt", "Latin", ("pt-BR-AntonioNeural",), ("pt-BR-FranciscaNeural",)),
    L("it", "Italian", "it", "Latin", ("it-IT-DiegoNeural",), ("it-IT-ElsaNeural",)),
    L("ru", "Russian", "ru", "Cyrillic", ("ru-RU-DmitryNeural",), ("ru-RU-SvetlanaNeural",)),
    L("ar", "Arabic", "ar", "Arabic", ("ar-SA-HamedNeural",), ("ar-SA-ZariyahNeural",)),
    L("ja", "Japanese", "ja", "Japanese", ("ja-JP-KeitaNeural",), ("ja-JP-NanamiNeural",)),
    L("ko", "Korean", "ko", "Hangul", ("ko-KR-InJoonNeural",), ("ko-KR-SunHiNeural",)),
    L("zh", "Chinese (Mandarin)", "zh", "Simplified Chinese", ("zh-CN-YunxiNeural",), ("zh-CN-XiaoxiaoNeural",)),
    L("tr", "Turkish", "tr", "Latin", ("tr-TR-AhmetNeural",), ("tr-TR-EmelNeural",)),
]}

# which open voice models speak what (codes as the models take them; mirrors the catalog's "languages")
CHATTERBOX = {"ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko", "ms", "nl", "no", "pl", "pt",
              "ru", "sv", "sw", "tr", "zh"}
INDICF5 = {"as", "bn", "gu", "hi", "kn", "ml", "mr", "or", "pa", "ta", "te"}
PARLER = {"as", "bn", "brx", "doi", "en", "gu", "hi", "kn", "kok", "mai", "ml", "mni", "mr", "ne", "or", "sa", "sat", "sd",
          "ta", "te", "ur"}


def get(code: str) -> Lang:
    if code in LANGS:
        return LANGS[code]
    base = (code or "en").split("-")[0].lower()
    if base in LANGS:
        return LANGS[base]
    # any other language: the models may still speak it; Edge falls back to English voices
    return Lang(code, code, base, "its usual script", LANGS["en"].edge_male, LANGS["en"].edge_female)


def line_models(code: str) -> list[str]:
    """Open models that can speak a line in this language, best first (both clone the approved sample)."""
    t = get(code).tts
    out = []
    if t in CHATTERBOX:
        out.append("chatterbox")
    if t in INDICF5:
        out.append("indicf5")
    if t in PARLER:
        out.append("indic-parler-tts")      # speaks from the voice description (no cloning): last resort
    return out


def design_models(code: str) -> list[str]:
    """Open models that can design a new voice from a description in this language."""
    return ["indic-parler-tts"] if get(code).tts in PARLER else []


def public() -> list[dict]:
    return [{"code": x.code, "name": x.name, "script": x.script, "lines": line_models(x.code),
             "design": design_models(x.code), "note": x.note} for x in LANGS.values()]
