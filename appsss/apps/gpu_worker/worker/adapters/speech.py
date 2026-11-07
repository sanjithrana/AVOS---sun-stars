"""Text-to-speech models inside the worker process (pip packages, no ComfyUI): the voices of a Series.

    chatterbox         Resemble AI Chatterbox Multilingual (MIT): 23 languages incl. Hindi and English; clones the
                       character's approved voice sample (inputs["audio"]) and takes an emotion level per line.
    indicf5            AI4Bharat IndicF5 (MIT, gated on Hugging Face): 11 Indian languages (Hindi, Tamil, Telugu,
                       Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese); clones the sample,
                       needs the sample's transcript (options["ref_text"]).
    indic-parler-tts   AI4Bharat Indic Parler-TTS (Apache-2.0, gated): designs a NEW voice from a description
                       ("a warm middle-aged woman, slightly fast, expressive"), 21 languages incl. English. AVOS uses it
                       to make each character's voice sample, which you approve; the lines are then cloned from it.

Job: task "speech", want "audio", prompt = the text to say, options = {language, ref_text, description,
exaggeration (0.25–2, emotion), cfg_weight}. Returns a WAV. Install on the GPU machine:

    pip install -r requirements-speech.txt

Weights download from Hugging Face on first use (HF_HOME; the two AI4Bharat models are gated: accept their terms
on huggingface.co and set HF_TOKEN). SPEECH_MODELS limits which ones this worker offers.
"""
from __future__ import annotations

import asyncio
import importlib.util
import io
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from worker.adapters.base import Adapter, JobSpec, Progress

CHATTERBOX_LANGS = {"ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja", "ko", "ms", "nl", "no", "pl",
                    "pt", "ru", "sv", "sw", "tr", "zh"}
MODELS: dict[str, dict[str, Any]] = {
    "chatterbox": {"package": "chatterbox", "repo": "ResembleAI/chatterbox"},
    "indicf5": {"package": "transformers", "repo": "ai4bharat/IndicF5", "extra": "f5_tts"},
    "indic-parler-tts": {"package": "parler_tts", "repo": "ai4bharat/indic-parler-tts"},
}


def _has(pkg: str) -> bool:
    try:
        return importlib.util.find_spec(pkg) is not None
    except (ImportError, ValueError):
        return False


def wav_bytes(samples: Any, sr: int) -> bytes:
    """float / int16 samples (numpy or torch, mono) → 16-bit WAV."""
    import numpy as np
    import soundfile as sf

    if hasattr(samples, "detach"):
        samples = samples.detach().cpu().float().numpy()
    a = np.asarray(samples)
    if a.dtype == np.int16:
        a = a.astype(np.float32) / 32768.0
    a = np.squeeze(a).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, np.clip(a, -1, 1), int(sr), format="WAV", subtype="PCM_16")
    return buf.getvalue()


class SpeechAdapter(Adapter):
    name = "speech"
    precisions = ("bf16",)
    offload = False

    def __init__(self) -> None:
        self.loaded: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _wanted(self) -> list[str]:
        only = {m.strip() for m in (os.getenv("SPEECH_MODELS") or "").split(",") if m.strip()}
        return [m for m in MODELS if not only or m in only]

    async def ready(self) -> tuple[bool, str | None]:
        if not _has("torch"):
            return False, "PyTorch isn't installed on this worker."
        if not self.models():
            return False, "No speech model is installed (pip install -r requirements-speech.txt on the GPU machine)."
        return True, None

    def models(self) -> list[str]:
        out = []
        for m in self._wanted():
            spec = MODELS[m]
            if _has(spec["package"]) and (not spec.get("extra") or _has(spec["extra"])):
                out.append(m)
        return out

    # ---- loading ----
    def _device(self) -> str:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"

    def _load_sync(self, model: str) -> Any:
        dev = self._device()
        if model == "chatterbox":
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            try:      # Multilingual V3 (2026) when the installed package has it
                return ChatterboxMultilingualTTS.from_pretrained(device=dev, t3_model="v3")
            except TypeError:
                return ChatterboxMultilingualTTS.from_pretrained(device=dev)
        if model == "indicf5":
            from transformers import AutoModel

            return AutoModel.from_pretrained(MODELS[model]["repo"], trust_remote_code=True).to(dev)
        if model == "indic-parler-tts":
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer

            repo = MODELS[model]["repo"]
            m = ParlerTTSForConditionalGeneration.from_pretrained(repo).to(dev)
            return {"model": m, "tok": AutoTokenizer.from_pretrained(repo),
                    "desc_tok": AutoTokenizer.from_pretrained(m.config.text_encoder._name_or_path)}
        raise RuntimeError(f"Unknown speech model {model}.")

    async def load(self, job: JobSpec, progress: Progress) -> None:
        if job.model in self.loaded:
            return
        await progress(0.0, f"loading {job.model}")
        self.loaded[job.model] = await asyncio.to_thread(self._load_sync, job.model)

    async def unload(self, model: str) -> None:
        if self.loaded.pop(model, None) is not None:
            try:
                import gc

                import torch

                gc.collect()
                torch.cuda.empty_cache()
            except ImportError:
                pass

    # ---- running ----
    def _run_sync(self, job: JobSpec) -> bytes:
        o = job.options or {}
        lang = str(o.get("language") or "en").split("-")[0].lower()
        text = (job.prompt or "").strip()
        if not text:
            raise RuntimeError("Nothing to say (empty text).")
        m = self.loaded[job.model]
        with tempfile.TemporaryDirectory() as t, self._lock:
            ref = None
            if job.inputs.get("audio"):
                ref = Path(t) / "voice.wav"
                ref.write_bytes(job.inputs["audio"])
            if job.model == "chatterbox":
                if lang not in CHATTERBOX_LANGS:
                    raise RuntimeError(f"Chatterbox doesn't speak '{lang}' (it has {', '.join(sorted(CHATTERBOX_LANGS))}).")
                kw: dict[str, Any] = {"language_id": lang, "exaggeration": float(o.get("exaggeration") or 0.5),
                                      "cfg_weight": float(o.get("cfg_weight") or 0.5)}
                if ref:
                    kw["audio_prompt_path"] = str(ref)
                return wav_bytes(m.generate(text, **kw), m.sr)
            if job.model == "indicf5":
                if not ref or not o.get("ref_text"):
                    raise RuntimeError("IndicF5 clones a voice: it needs the voice sample and its transcript (ref_text).")
                return wav_bytes(m(text, ref_audio_path=str(ref), ref_text=str(o["ref_text"])), 24000)
            # indic-parler-tts: a voice from a description
            import torch

            desc = str(o.get("description") or "A clear, expressive voice, close to the microphone, no background noise.")
            dev = self._device()
            d = m["desc_tok"](desc, return_tensors="pt").to(dev)
            p = m["tok"](text, return_tensors="pt").to(dev)
            if job.seed is not None:
                torch.manual_seed(int(job.seed))
            audio = m["model"].generate(input_ids=d.input_ids, attention_mask=d.attention_mask,
                                        prompt_input_ids=p.input_ids, prompt_attention_mask=p.attention_mask)
            return wav_bytes(audio, m["model"].config.sampling_rate)

    async def run(self, job: JobSpec, progress: Progress) -> tuple[bytes, str]:
        await progress(0.1, f"{job.model}: speaking {len(job.prompt or '')} characters")
        return await asyncio.to_thread(self._run_sync, job), "wav"

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "languages": {"chatterbox": sorted(CHATTERBOX_LANGS)}}
