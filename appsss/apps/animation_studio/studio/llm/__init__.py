"""The AI crew: one interface over local and hosted models.

Local first: Ollama runs on your own computer (free). Optional: free-tier cloud
(Groq, Gemini, OpenRouter), paid APIs (OpenAI, Anthropic) and the original
ReelMimic crews (Claude Code / Codex CLIs, using your own login). "builtin"
runs with no AI at all: the engine's own rules (useful offline and for tests).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

import httpx

from .. import avos_settings, config

AGENT_KINDS = ("ollama", "llamacpp", "colibri", "groq", "gemini", "openrouter", "openai", "anthropic", "claude", "codex", "builtin")

SPEC: dict[str, dict] = {
    "ollama": {"label": "Ollama (local)", "tier": "local", "model": "qwen2.5:7b",
               "models": ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "gemma3:12b", "qwen2.5vl:7b", "llava:7b"]},
    "llamacpp": {"label": "llama.cpp (local GGUF)", "tier": "local", "model": "local", "local": True,
                 "models": ["local"],
                 "fix": "Run llama.cpp's server with a small GGUF model on this computer, e.g. `llama-server -m qwen2.5-7b-instruct-q4_k_m.gguf --port 8080`, or set its address (LLAMACPP_URL)."},
    "colibri": {"label": "Colibrì (local MoE)", "tier": "local", "model": "local", "local": True, "models": ["local"],
                "fix": "Run Colibrì's server on this computer: `coli serve --model <path to the model>` (OpenAI API on port 8000; "
                       "github.com/JustVugg/colibri), or set its address (COLIBRI_URL). It streams huge MoE models from your SSD "
                       "on a CPU: excellent writing, a few words per second, so long answers take minutes."},
    "groq": {"label": "Groq", "tier": "free", "key": "GROQ_API_KEY", "model": "openai/gpt-oss-120b",
             "base": "https://api.groq.com/openai/v1", "models": ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"],
             "fix": "Free key (no card) at console.groq.com/keys, paste it here."},
    "gemini": {"label": "Gemini", "tier": "free", "key": "GEMINI_API_KEY", "model": "gemini-2.5-flash",
               "base": "https://generativelanguage.googleapis.com/v1beta/openai", "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
               "fix": "Free key at aistudio.google.com/apikey, paste it here."},
    "openrouter": {"label": "OpenRouter", "tier": "free", "key": "OPENROUTER_API_KEY", "model": "meta-llama/llama-3.3-70b-instruct:free",
                   "base": "https://openrouter.ai/api/v1", "models": ["meta-llama/llama-3.3-70b-instruct:free", "qwen/qwen-2.5-72b-instruct:free", "google/gemini-2.0-flash-exp:free"],
                   "fix": "Key at openrouter.ai/keys (\":free\" models cost nothing), paste it here."},
    "openai": {"label": "OpenAI", "tier": "paid", "key": "OPENAI_API_KEY", "model": "gpt-4o-mini",
               "base": "https://api.openai.com/v1", "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
               "fix": "Paid. Key at platform.openai.com/api-keys, paste it here."},
    "anthropic": {"label": "Anthropic API", "tier": "paid", "key": "ANTHROPIC_API_KEY", "model": "claude-sonnet-4-5",
                  "models": ["claude-sonnet-4-5", "claude-haiku-4-5", "claude-opus-4-1"],
                  "fix": "Paid. Key at console.anthropic.com, paste it here."},
    "claude": {"label": "Claude Code", "tier": "paid", "fix": "Install Claude Code (npm i -g @anthropic-ai/claude-code) on the computer running this service and log in once with `claude`. Uses your Claude plan."},
    "codex": {"label": "Codex", "tier": "paid", "fix": "Install Codex CLI (npm i -g @openai/codex) on the computer running this service and run `codex login`. Uses your ChatGPT plan."},
    "builtin": {"label": "Built-in rules (no AI)", "tier": "local", "fix": ""},
}
VISION_RX = re.compile(r"vl|llava|vision|gemma3|minicpm-v|moondream|llama-4|gpt-4o|gpt-4\.1|gemini|claude|pixtral|bakllava", re.I)


def custom_llms() -> list[dict]:
    """Text models added on the AVOS Settings page (any OpenAI-compatible API), usable as crews."""
    return avos_settings.custom_models("llm")


def agent_kinds() -> tuple[str, ...]:
    return (*AGENT_KINDS, *[m["id"] for m in custom_llms()])


def spec(kind: str) -> dict:
    if kind in SPEC:
        return SPEC[kind]
    c = avos_settings.custom_model(kind)
    if c and c["task"] == "llm":
        return {"label": c["name"], "tier": "custom", "key": c.get("key_env") or "", "model": c["model"], "base": c["base_url"],
                "models": [c["model"]], "custom": True,
                "fix": f"Add the {c.get('key_env')} key in Settings → API keys." if c.get("key_env") else "Check that the server is running."}
    return {"label": kind, "tier": "custom", "model": ""}


# Models a provider has shut down → what it says to use instead (Groq retired Llama 3.x on 2026-08-16, Qwen 3.6 on
# 2026-09-14). A model saved in AI settings that is on this list is upgraded silently; anything else that disappears
# is caught at call time (see _openai_compat: the crew asks the provider for its models and switches).
RETIRED = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b": "qwen/qwen3.8-27b",
}


def model_of(kind: str) -> str:
    if kind not in SPEC:
        return spec(kind).get("model", "")
    m = os.environ.get(f"STUDIO_{kind.upper()}_MODEL") or SPEC.get(kind, {}).get("model", "")
    return RETIRED.get(m, m)


async def available_models(kind: str) -> list[str] | None:
    """The model ids an OpenAI-compatible provider offers this key right now (GET /models), or None."""
    s = spec(kind)
    base = f"{local_url(kind)}/v1" if kind in LOCAL_SERVERS else s.get("base")
    key = os.environ.get(s["key"]) if s.get("key") else "none"
    if not base or not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            return [m.get("id", "") for m in r.json().get("data") or [] if m.get("id")]
    except Exception:
        return None


def _usable_text_model(kind: str, ids: list[str]) -> str | None:
    """Pick a replacement: our suggestions first, then a general chat model the provider lists."""
    for m in SPEC.get(kind, {}).get("models", []):
        if m in ids:
            return m
    skip = ("whisper", "tts", "guard", "embed", "vision", "audio", "playai", "orpheus", "compound", "safeguard")
    chat = [i for i in ids if not any(x in i.lower() for x in skip)]
    for pref in ("gpt-oss-120b", "qwen3", "llama-4", "gpt-oss", "llama", "mixtral", "gemma"):
        hit = next((i for i in chat if pref in i.lower()), None)
        if hit:
            return hit
    return chat[0] if chat else None


def ollama_url() -> str:
    in_docker = os.path.exists("/.dockerenv")
    return (os.environ.get("OLLAMA_URL") or os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST_URL")
            or ("http://host.docker.internal:11434" if in_docker else "http://127.0.0.1:11434")).rstrip("/")


LOCAL_SERVERS = {"llamacpp": ("LLAMACPP_URL", 8080), "colibri": ("COLIBRI_URL", 8000)}   # OpenAI-compatible servers on this PC


def local_url(kind: str) -> str:
    env, port = LOCAL_SERVERS[kind]
    in_docker = os.path.exists("/.dockerenv")
    return (os.environ.get(env) or (f"http://host.docker.internal:{port}" if in_docker else f"http://127.0.0.1:{port}")).rstrip("/")


def llamacpp_url() -> str:
    return local_url("llamacpp")


async def local_models(kind: str) -> list[str] | None:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{local_url(kind)}/v1/models")
            r.raise_for_status()
            return [m.get("id", "") for m in r.json().get("data") or []]
    except Exception:
        return None


async def llamacpp_models() -> list[str] | None:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{llamacpp_url()}/v1/models")
            r.raise_for_status()
            return [m.get("id", "") for m in r.json().get("data") or []]
    except Exception:
        return None


def default_agent() -> str:
    a = os.environ.get("STUDIO_DEFAULT_AGENT") or "ollama"
    return a if a in agent_kinds() else "ollama"


def _cli(kind: str) -> str | None:
    if kind == "codex":
        return os.environ.get("CODEX_BIN") or shutil.which("codex")
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude")


_CLI_VERSION: dict[str, tuple[float, str | None]] = {}


def _cli_version(kind: str) -> str | None:
    hit = _CLI_VERSION.get(kind)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    exe = _cli(kind)
    v = None
    if exe:
        try:
            r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20)
            v = (r.stdout or r.stderr).strip().splitlines()[0][:60] if r.returncode == 0 else None
        except Exception:
            v = None
    _CLI_VERSION[kind] = (time.time(), v)
    return v


async def ollama_models() -> list[dict] | None:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{ollama_url()}/api/tags")
            r.raise_for_status()
            return r.json().get("models") or []
    except Exception:
        return None


def _has_model(models: list[dict], want: str) -> bool:
    names = {m.get("name", "") for m in models} | {m.get("model", "") for m in models}
    return want in names or f"{want}:latest" in names or any(n.split(":")[0] == want for n in names if ":" not in want)


PULLS: dict[str, dict] = {}


async def agents_info() -> dict:
    avos_settings.apply()
    out = []
    models = await ollama_models()
    for kind in agent_kinds():
        s = spec(kind)
        info: dict[str, Any] = {"id": kind, "label": s["label"], "tier": s["tier"]}
        if kind == "ollama":
            m = model_of(kind)
            vis = os.environ.get("STUDIO_OLLAMA_VISION_MODEL") or ""
            have = [x.get("name", "") for x in models or []]
            info.update(model=m, url=ollama_url(), models=sorted(set(have)) or s["models"], suggested=s["models"])
            if models is None:
                info.update(ready=False, detail=f"Ollama isn't running at {ollama_url()}",
                            fix=f"Install Ollama from ollama.com and start it (`ollama serve`), then download a model: `ollama pull {m}`.")
            elif not _has_model(models, m):
                info.update(ready=False, detail=f"Model {m} isn't downloaded yet", fix=f"Click Download, or run `ollama pull {m}`.")
            else:
                info.update(ready=True, detail=m + (f" · looks at frames with {vis}" if vis and _has_model(models, vis) else ""))
            info["vision"] = bool(VISION_RX.search(m)) or bool(vis and models and _has_model(models, vis))
            info["visionModel"] = vis
        elif kind in LOCAL_SERVERS:
            have = await local_models(kind)
            m = (have or ["local"])[0]
            name = s["label"].split(" (")[0]
            info.update(model=m, url=local_url(kind), models=have or s["models"], needsKey=False, ready=have is not None,
                        detail=f"{m} · {local_url(kind)}" if have is not None else f"{name} isn't running at {local_url(kind)}",
                        fix=s["fix"], vision=bool(VISION_RX.search(m)) or (kind == "colibri" and "vision" in m.lower()))
        elif kind in ("claude", "codex"):
            v = _cli_version(kind)
            info.update(ready=bool(v), detail=v or "Not installed on the computer running this service", fix=s["fix"], vision=True)
        elif kind == "builtin":
            info.update(ready=True, detail="No AI: plans and reviews come from the engine's own rules", vision=False)
        elif s.get("custom"):
            has = bool(not s["key"] or os.environ.get(s["key"]))
            info.update(model=s["model"], models=s["models"], needsKey=bool(s["key"]), hasKey=bool(s["key"] and os.environ.get(s["key"])),
                        ready=has, detail=f"{s['model']} · {s['base']}" if has else f"No {s['key']} key yet", fix=s["fix"],
                        vision=bool(VISION_RX.search(s["model"])), custom=True)
        else:
            has = bool(os.environ.get(s["key"]))
            m = model_of(kind)
            info.update(model=m, models=s["models"], needsKey=True, hasKey=has, ready=has,
                        detail=m if has else "No API key yet", fix=s["fix"], vision=bool(VISION_RX.search(m)))
        out.append(info)
    from .. import models
    from ..render.images import image_model, images_status
    rs = config.render_settings()
    ok, detail = images_status()
    return {"default": default_agent(), "agents": out, "pulls": PULLS,
            "render": {**rs, "imagesReady": ok, "imagesDetail": detail, "imageModel": image_model()},
            "models": models.status()}


async def agent_status() -> dict:
    info = await agents_info()
    return {a["id"]: (a["detail"] if a["ready"] else None) for a in info["agents"]}


def save_agent_settings(body: dict) -> None:
    upd: dict[str, Any] = {}
    shared: dict[str, Any] = {}   # keys and the GPU server are shared with the Facts tab (AVOS Settings)
    agent = body.get("agent")
    if agent is not None and agent not in agent_kinds():
        raise ValueError("unknown agent")
    if body.get("default") is not None:
        if body["default"] not in agent_kinds():
            raise ValueError("unknown agent")
        upd["STUDIO_DEFAULT_AGENT"] = body["default"]
    if agent:
        if "model" in body and body["model"] is not None and agent in SPEC:
            upd[f"STUDIO_{agent.upper()}_MODEL"] = str(body["model"]).strip()
        if "key" in body and spec(agent).get("key"):
            shared[spec(agent)["key"]] = str(body["key"] or "").strip()
        if "url" in body and agent == "ollama":
            upd["OLLAMA_URL"] = str(body["url"] or "").strip()
        if "visionModel" in body and agent == "ollama":
            upd["STUDIO_OLLAMA_VISION_MODEL"] = str(body["visionModel"] or "").strip()
    r = body.get("render") or {}
    if r.get("quality") in ("720p", "1080p"):
        upd["STUDIO_QUALITY"] = r["quality"]
    if r.get("images") in ("drawn", "ai"):
        upd["STUDIO_IMAGES"] = r["images"]
    from ..models import image_choices
    IMAGE_CHOICES = image_choices()
    if r.get("imageModel") is not None:
        if r["imageModel"] not in IMAGE_CHOICES:
            raise ValueError(f"imageModel must be one of {', '.join(IMAGE_CHOICES)}")
        upd["STUDIO_IMAGE_MODEL"] = r["imageModel"]
    m = body.get("models") or {}
    if "falKey" in m:
        shared["FAL_KEY"] = str(m["falKey"] or "").strip()
    if "comfyuiUrl" in m:
        url = str(m["comfyuiUrl"] or "").strip()
        if url and not re.match(r"^https?://", url):
            raise ValueError("ComfyUI address must start with http:// or https://")
        config.forget_secrets(["COMFYUI_URL"])   # older versions kept it in the studio's own file
        avos_settings.set_gpu(url, None)
    if shared:
        config.forget_secrets(list(shared))
        avos_settings.set_env(shared)
    if upd:
        config.save_secrets(upd)


async def pull_model(model: str) -> None:
    PULLS[model] = {"status": "starting", "done": False, "pct": 0}
    try:
        async with httpx.AsyncClient(timeout=None) as c:
            async with c.stream("POST", f"{ollama_url()}/api/pull", json={"name": model, "stream": True}) as r:
                if r.status_code >= 400:
                    raise RuntimeError((await r.aread()).decode(errors="replace")[:300])
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    ev = json.loads(line)
                    if ev.get("error"):
                        raise RuntimeError(ev["error"])
                    st = {"status": ev.get("status", ""), "done": False}
                    if ev.get("total"):
                        st["pct"] = round(100 * (ev.get("completed") or 0) / ev["total"], 1)
                    PULLS[model] = {**PULLS[model], **st}
        PULLS[model] = {"status": "success", "done": True, "pct": 100}
    except Exception as e:
        PULLS[model] = {"status": "failed", "done": True, "error": f"{e}" or "pull failed"}


# ---------- the crew used by the director ----------
class CrewError(RuntimeError):
    pass


def _img_b64(p: Path, max_side: int = 1280) -> str:
    from PIL import Image
    import io
    im = Image.open(p).convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def extract_json(text: str | None) -> Any:
    """The first JSON object/array in a model reply (tolerates code fences and chatter)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    for open_, close in (("{", "}"), ("[", "]")):
        start = t.find(open_)
        while start >= 0:
            depth, ins, esc = 0, False, False
            for i in range(start, len(t)):
                ch = t[i]
                if ins:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        ins = False
                elif ch == '"':
                    ins = True
                elif ch == open_:
                    depth += 1
                elif ch == close:
                    depth -= 1
                    if depth == 0:
                        chunk = t[start:i + 1]
                        try:
                            return json.loads(chunk)
                        except Exception:
                            try:
                                return json.loads(re.sub(r",\s*([}\]])", r"\1", chunk))
                            except Exception:
                                break
            start = t.find(open_, start + 1)
    return None


class Crew:
    """One agent role on one project. Keeps its own conversation (director, builders) unless it is a fresh reviewer."""

    def __init__(self, kind: str, jid: str, session: str, who: str, log: Callable[[dict], None], abort: Any, project_dir: Path):
        self.kind, self.jid, self.session, self.who, self._log, self.abort = kind, jid, session, who, log, abort
        self.dir = project_dir
        self.fresh = session == "fresh"
        self.hist_path = project_dir / "sessions" / f"{session}.json"
        self.calls = 0

    # ----- history -----
    def history(self) -> list[dict]:
        if self.fresh:
            return []
        try:
            return json.loads(self.hist_path.read_text("utf-8"))[-8:]
        except Exception:
            return []

    def remember(self, prompt: str, answer: str) -> None:
        if self.fresh:
            return
        h = self.history() + [{"role": "user", "content": prompt[-4000:]}, {"role": "assistant", "content": answer[-3000:]}]
        self.hist_path.parent.mkdir(parents=True, exist_ok=True)
        self.hist_path.write_text(json.dumps(h[-8:], ensure_ascii=False), "utf-8")

    @property
    def enabled(self) -> bool:
        return self.kind != "builtin"

    def vision(self) -> bool:
        if self.kind == "ollama":
            return bool(VISION_RX.search(model_of("ollama")) or os.environ.get("STUDIO_OLLAMA_VISION_MODEL"))
        if self.kind in ("claude", "codex", "builtin"):
            return self.kind != "builtin"
        return bool(VISION_RX.search(model_of(self.kind)))

    def log(self, ev: dict) -> None:
        self._log({**ev, "who": self.who})

    # ----- calls -----
    async def ask(self, system: str, prompt: str, images: list[Path] | None = None, want_json: bool = True,
                  temperature: float = 0.6, max_tokens: int = 3000, keep: bool = True) -> str | None:
        if not self.enabled or self.abort.aborted:
            return None
        avos_settings.apply()
        images = [p for p in images or [] if Path(p).exists()] if self.vision() else []
        self.calls += 1
        t0 = time.time()
        try:
            if self.kind == "ollama":
                try:
                    text = await self._ollama(system, prompt, images, want_json, temperature, max_tokens)
                except CrewError as e:
                    vis = os.environ.get("STUDIO_OLLAMA_VISION_MODEL")
                    if not (images and vis and vis in str(e) and "isn't downloaded" in str(e)):
                        raise
                    # the vision model isn't there yet: review with the text model (measurements still apply)
                    self.log({"type": "error", "text": f"{e} Checking without looking at the frames this time."})
                    text = await self._ollama(system, prompt, [], want_json, temperature, max_tokens)
            elif self.kind in ("llamacpp", "colibri", "groq", "gemini", "openrouter", "openai") or spec(self.kind).get("custom"):
                text = await self._openai_compat(system, prompt, images, want_json, temperature, max_tokens)
            elif self.kind == "anthropic":
                text = await self._anthropic(system, prompt, images, temperature, max_tokens)
            elif self.kind == "claude":
                text = await self._claude_cli(system, prompt, images)
            elif self.kind == "codex":
                text = await self._codex_cli(system, prompt, images)
            else:
                return None
        except CrewError:
            raise
        except httpx.ConnectError as e:
            raise CrewError(self._unreachable(e))
        except httpx.HTTPStatusError as e:
            body = e.response.text[:400]
            raise CrewError(f"{spec(self.kind)['label']} answered {e.response.status_code}: {body}")
        except httpx.TimeoutException:
            raise CrewError(f"{spec(self.kind)['label']} took too long to answer")
        if text and keep:
            self.remember(prompt, text)
        self.log({"type": "tool", "name": "LLM", "detail": f"{spec(self.kind)['label']} · {model_of(self.kind) or self.kind} · {len(text or '')} chars · {time.time() - t0:.0f}s"})
        return text

    def _unreachable(self, e: Exception) -> str:
        if self.kind == "ollama":
            return (f"Ollama isn't reachable at {ollama_url()} ({e}). Start Ollama (`ollama serve`) and download the model "
                    f"(`ollama pull {model_of('ollama')}`), or pick another AI crew.")
        return f"{spec(self.kind)['label']} isn't reachable ({e})"

    async def ask_json(self, system: str, prompt: str, images: list[Path] | None = None, temperature: float = 0.5,
                       max_tokens: int = 3500, keep: bool = True) -> Any:
        """A JSON answer, or None (the caller then uses the engine's own draft). One retry on unparseable output."""
        if not self.enabled:
            return None
        sys2 = system + "\nReply with ONE valid JSON value only. No markdown, no comments."
        for attempt in range(2):
            text = await self.ask(sys2, prompt if attempt == 0 else prompt + "\n\nYour last reply was not valid JSON. Reply with valid JSON only.",
                                  images=images, want_json=True, temperature=temperature, max_tokens=max_tokens, keep=keep)
            data = extract_json(text)
            if data is not None:
                if isinstance(data, dict) and isinstance(data.get("thinking"), str) and data["thinking"].strip():
                    self.log({"type": "thinking", "text": data["thinking"].strip()[:1200]})
                return data
            if self.abort.aborted:
                return None
        self.log({"type": "error", "text": "The AI's answer wasn't valid JSON twice; using the engine's own draft for this part."})
        return None

    def _messages(self, system: str, prompt: str) -> list[dict]:
        return [{"role": "system", "content": system}, *self.history(), {"role": "user", "content": prompt}]

    async def _stream_thinking(self, chunks: Any, want_json: bool) -> str:
        """Collect streamed text; non-JSON replies are shown as live thinking."""
        out, buf, last = [], "", time.time()
        async for piece in chunks:
            if self.abort.aborted:
                raise CrewError("cancelled")
            out.append(piece)
            if not want_json:
                buf += piece
                if len(buf) > 280 or ("\n" in buf and len(buf) > 60) or time.time() - last > 4:
                    self.log({"type": "thinking", "text": buf.strip()})
                    buf, last = "", time.time()
        if buf.strip() and not want_json:
            self.log({"type": "thinking", "text": buf.strip()})
        return "".join(out)

    async def _ollama(self, system: str, prompt: str, images: list[Path], want_json: bool, temperature: float, max_tokens: int) -> str:
        model = model_of("ollama")
        vis = os.environ.get("STUDIO_OLLAMA_VISION_MODEL")
        if images and vis and not VISION_RX.search(model):
            model = vis
        msgs = self._messages(system, prompt)
        if images:
            msgs[-1]["images"] = [_img_b64(p) for p in images[:4]]
        body: dict[str, Any] = {"model": model, "messages": msgs, "stream": True,
                                "options": {"temperature": temperature, "num_ctx": int(os.environ.get("STUDIO_OLLAMA_CTX", 8192)), "num_predict": max_tokens}}
        if want_json:
            body["format"] = "json"

        async def gen():
            async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5)) as c:
                async with c.stream("POST", f"{ollama_url()}/api/chat", json=body) as r:
                    if r.status_code >= 400:
                        txt = (await r.aread()).decode(errors="replace")
                        if "not found" in txt:
                            raise CrewError(f"Ollama model {model} isn't downloaded. Run `ollama pull {model}` or click Download in AI settings.")
                        raise CrewError(f"Ollama error {r.status_code}: {txt[:300]}")
                    async for line in r.aiter_lines():
                        if line.strip():
                            ev = json.loads(line)
                            if ev.get("error"):
                                raise CrewError(f"Ollama: {ev['error']}")
                            yield (ev.get("message") or {}).get("content", "")
        return await self._stream_thinking(gen(), want_json)

    async def _openai_compat(self, system: str, prompt: str, images: list[Path], want_json: bool, temperature: float, max_tokens: int) -> str:
        s = spec(self.kind)
        if self.kind in LOCAL_SERVERS:
            s = {**s, "base": f"{local_url(self.kind)}/v1"}
        key = os.environ.get(s["key"]) if s.get("key") else ("none" if s.get("custom") or s.get("local") else None)
        if not key:
            raise CrewError(f"No {s['label']} API key. Add it in AI settings.")
        msgs = self._messages(system, prompt)
        if images:
            msgs[-1]["content"] = [{"type": "text", "text": prompt}] + [
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + _img_b64(p)}} for p in images[:4]]
        model = model_of(self.kind)
        if self.kind in LOCAL_SERVERS and model == "local":
            model = ((await local_models(self.kind)) or ["local"])[0]      # the model the local server has loaded
        body: dict[str, Any] = {"model": model, "messages": msgs, "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        if want_json and self.kind in ("openai", "groq", "gemini"):
            body["response_format"] = {"type": "json_object"}
        if self.kind == "groq" and "gpt-oss" in body["model"]:
            # gpt-oss thinks before answering and the thinking counts against max_tokens: keep it short so long
            # JSON answers (Series scripts) aren't cut off
            body["reasoning_effort"] = os.environ.get("STUDIO_REASONING_EFFORT") or "low"

        async def gen():
            async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as c:
              for attempt in range(2):
                async with c.stream("POST", f"{s['base']}/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"}) as r:
                    if r.status_code >= 400:
                        txt = (await r.aread()).decode(errors="replace")
                        gone = r.status_code in (400, 404) and ("model_not_found" in txt or "decommissioned" in txt
                                                                or "does not exist" in txt or "not a valid model" in txt
                                                                or "No endpoints found" in txt)
                        if gone and attempt == 0:
                            # the provider retired this model: ask it what it has now and switch (and remember it)
                            ids = await available_models(self.kind) or []
                            new = _usable_text_model(self.kind, ids)
                            if new and new != body["model"]:
                                self.log({"type": "text", "text": f"{s['label']} no longer offers {body['model']}; "
                                                                  f"switched to {new}."})
                                old_model, body["model"] = body["model"], new
                                if self.kind in SPEC:
                                    config.save_secrets({f"STUDIO_{self.kind.upper()}_MODEL": new})
                                    os.environ[f"STUDIO_{self.kind.upper()}_MODEL"] = new
                                continue
                        raise CrewError(f"{s['label']} error {r.status_code}: {txt[:400]}")
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            ev = json.loads(data)
                        except Exception:
                            continue
                        for ch in ev.get("choices") or []:
                            yield (ch.get("delta") or {}).get("content") or ""
                    return
        return await self._stream_thinking(gen(), want_json)

    async def _anthropic(self, system: str, prompt: str, images: list[Path], temperature: float, max_tokens: int) -> str:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise CrewError("No Anthropic API key. Add it in AI settings.")
        hist = [m for m in self.history() if m["role"] in ("user", "assistant")]
        content: Any = prompt
        if images:
            content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _img_b64(p)}} for p in images[:4]] + [{"type": "text", "text": prompt}]
        body = {"model": model_of("anthropic"), "system": system, "max_tokens": max_tokens, "temperature": temperature,
                "messages": hist + [{"role": "user", "content": content}]}
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=10)) as c:
            r = await c.post("https://api.anthropic.com/v1/messages", json=body,
                             headers={"x-api-key": key, "anthropic-version": "2023-06-01"})
            if r.status_code >= 400:
                raise CrewError(f"Anthropic error {r.status_code}: {r.text[:400]}")
            return "".join(b.get("text", "") for b in r.json().get("content") or [])

    async def _run_cli(self, cmd: list[str], stdin: str) -> tuple[int, str, str]:
        def go() -> tuple[int, str, str]:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 encoding="utf-8", errors="replace", cwd=str(self.dir))
            self.abort.procs.append(p)
            out, err = p.communicate(stdin, timeout=1800)
            return p.returncode, out, err
        return await asyncio.to_thread(go)

    def _sid(self) -> str | None:
        if self.fresh:
            return None
        try:
            return json.loads((self.dir / "sessions" / f"{self.session}.cli.json").read_text("utf-8")).get(self.kind)
        except Exception:
            return None

    def _save_sid(self, sid: str | None) -> None:
        if self.fresh or not sid:
            return
        p = self.dir / "sessions" / f"{self.session}.cli.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({self.kind: sid}), "utf-8")

    async def _claude_cli(self, system: str, prompt: str, images: list[Path]) -> str:
        exe = _cli("claude")
        if not exe:
            raise CrewError(SPEC["claude"]["fix"])
        full = f"{system}\n\n{prompt}"
        if images:
            full += "\n\nLook at these image files first (use the Read tool):\n" + "\n".join(str(Path(p).resolve()) for p in images)
        cmd = [exe, "-p", "--output-format", "json", "--allowedTools", "Read"]
        if (sid := self._sid()):
            cmd += ["--resume", sid]
        code, out, err = await self._run_cli(cmd, full)
        try:
            j = json.loads(out.strip().splitlines()[-1])
        except Exception:
            raise CrewError(f"Claude Code failed: {(err or out)[-400:]}")
        self._save_sid(j.get("session_id"))
        if j.get("is_error"):
            raise CrewError(f"Claude Code: {j.get('result') or err[-300:]}")
        return j.get("result") or ""

    async def _codex_cli(self, system: str, prompt: str, images: list[Path]) -> str:
        exe = _cli("codex")
        if not exe:
            raise CrewError(SPEC["codex"]["fix"])
        sid = self._sid()
        cmd = [exe, "exec"] + (["resume", sid] if sid else []) + ["--json", "--skip-git-repo-check"]
        for p in images:
            cmd += ["-i", str(Path(p).resolve())]
        cmd.append("-")
        code, out, err = await self._run_cli(cmd, f"{system}\n\n{prompt}")
        text, thread = "", None
        for line in out.splitlines():
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "thread.started":
                thread = ev.get("thread_id")
            item = ev.get("item") or {}
            if ev.get("type") == "item.completed" and item.get("type") in ("agent_message", "assistant_message"):
                text = item.get("text") or text
            if ev.get("type") in ("error", "turn.failed"):
                raise CrewError(f"Codex: {json.dumps(ev)[:400]}")
        self._save_sid(thread)
        if not text and code:
            raise CrewError(f"Codex failed: {err[-400:]}")
        return text
