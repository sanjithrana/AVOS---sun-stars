"""Watch live streams and turn the moments chat goes wild into clips.

For every streamer in the list: check every minute whether they are live, record the stream in 10-second pieces (streamlink -> ffmpeg), read Twitch chat
anonymously, and count messages in 5-second buckets. A bucket is a spike when chat is far above its own recent normal (several rules must hold at once, so one
busy second does not fire). Streams with no chat reader fall back to a loudness jump. 45 seconds after a spike the pieces from 75 s before to 45 s after are
joined and handed to the normal Auto Clip pipeline as a new job (captions, layout, effects, title). Nothing is ever posted from here: the clips wait in the Library.

The detector, the chat counter and the window maths are plain functions so they are tested without a network."""
from __future__ import annotations

import json
import re
import shutil
import socket
import ssl
import statistics
import subprocess
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

from . import rights, store

PLATFORMS = ("twitch", "youtube", "kick")
BUCKET = 5.0                 # seconds of chat per count
SEGMENT = 10                 # seconds per recorded piece
BOTS = {"nightbot", "streamelements", "moobot", "fossabot", "wizebot", "streamlabs", "soundalerts", "sery_bot"}
HYPE_WORDS = {"lol", "lmao", "lmfao", "omg", "wtf", "pog", "poggers", "kekw", "omegalul", "clip", "clipit", "no", "nooo", "noooo", "wow", "insane", "crazy", "dead", "rip", "bruh", "holy"}
DEFAULT_SETTINGS = {"pre": 75, "post": 45, "keep_hours": 1, "parallel": 2, "per_hour": 6, "baseline": 60, "warmup": 12, "cooldown": 90,
                    "k": 2.5, "ratio": 2.0, "uniq": 0.5, "audio_z": 3.5, "preset": "gta6"}
LOCK = threading.RLock()


# ---------- storage ----------
def _dir() -> Path:
    d = store.ROOT / "live"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load() -> dict:
    d = store._read(_dir() / "live.json", {})
    d.setdefault("streamers", [])
    d.setdefault("running", False)
    d["settings"] = {**DEFAULT_SETTINGS, **(d.get("settings") or {})}
    return d


def _save(d: dict) -> None:
    store._write(_dir() / "live.json", d)


def clean_handle(platform: str, raw: str) -> str:
    h = str(raw or "").strip()
    h = re.sub(r"^https?://(www\.)?(twitch\.tv|kick\.com|youtube\.com)/", "", h, flags=re.I).strip("/")
    h = re.sub(r"/live$", "", h)
    return re.sub(r"[^\w@.\-]", "", h)[:60]


def url_for(s: dict) -> str:
    h = s["handle"]
    if s["platform"] == "twitch":
        return f"https://www.twitch.tv/{h}"
    if s["platform"] == "kick":
        return f"https://kick.com/{h}"
    return f"https://www.youtube.com/{h if h.startswith('@') else '@' + h}/live"


def save_streamers(rows: list[dict]) -> list[dict]:
    out, seen = [], set()
    for r in rows[:60]:
        plat = r.get("platform") if r.get("platform") in PLATFORMS else "twitch"
        h = clean_handle(plat, r.get("handle"))
        if not h or (plat, h.lower()) in seen:
            continue
        seen.add((plat, h.lower()))
        try:
            mm = max(3, min(200, int(float(r.get("min_messages") or 10))))
        except (TypeError, ValueError):
            mm = 10
        out.append({"id": f"{plat}-{h.lower()}", "platform": plat, "handle": h, "min_messages": mm, "lang": "hi" if r.get("lang") == "hi" else "en",
                    "permission": bool(r.get("permission")), "on": r.get("on", True) is not False})
    with LOCK:
        d = load()
        d["streamers"] = out
        _save(d)
    return out


# ---------- chat ----------
def parse_irc(line: str) -> tuple[str, str] | None:
    """(user, text) of a PRIVMSG line, else None."""
    m = re.match(r"^(?:@\S+ )?:([^!\s]+)![^ ]+ PRIVMSG #\S+ :(.*)$", line.strip())
    return (m.group(1).lower(), m.group(2)) if m else None


class ChatCounter:
    """Counts chat for one 5-second bucket: at most 2 messages per person, no '!' commands, no known bots."""

    def __init__(self) -> None:
        self.per: Counter = Counter()
        self.words: Counter = Counter()
        self.samples: list[str] = []
        self.lock = threading.Lock()

    def add(self, user: str, text: str) -> None:
        text = text.strip()
        if not text or text.startswith("!") or user.lower() in BOTS:
            return
        with self.lock:
            if self.per[user] >= 2:
                return
            self.per[user] += 1
            for w in re.findall(r"[a-z']+", text.lower()):
                if len(w) > 1:
                    self.words[w] += 1
            if len(self.samples) < 3:
                self.samples.append(text[:80])

    def flush(self) -> dict:
        with self.lock:
            n, u = sum(self.per.values()), len(self.per)
            hype = sum(c for w, c in self.words.items() if w in HYPE_WORDS)
            top = [w for w, _ in self.words.most_common(3)]
            s = self.samples
            self.per, self.words, self.samples = Counter(), Counter(), []
        return {"count": n, "unique": u, "hype": hype, "top": top, "samples": s}


class Detector:
    """Chat spike rule from the playbook: count >= mean + k*std, >= ratio*median, >= min_messages, unique/count >= uniq, after a warm-up and outside the cooldown."""

    def __init__(self, min_messages: int = 10, **cfg: Any) -> None:
        c = {**DEFAULT_SETTINGS, **cfg}
        self.min, self.base, self.warm, self.cool = min_messages, int(c["baseline"]), int(c["warmup"]), float(c["cooldown"])
        self.k, self.ratio, self.uniq, self.audio_z = float(c["k"]), float(c["ratio"]), float(c["uniq"]), float(c["audio_z"])
        self.hist: deque = deque(maxlen=self.base)
        self.until = 0.0
        self.loud: deque = deque(maxlen=600)
        self.run = 0

    def push(self, t: float, b: dict, audio_z: float = 0.0) -> dict | None:
        count, uniq = b["count"], b["unique"]
        fire = None
        if len(self.hist) >= self.warm and t >= self.until:
            mean = statistics.fmean(self.hist)
            std = statistics.pstdev(self.hist)
            med = statistics.median(self.hist)
            if count >= mean + self.k * std and count >= self.ratio * max(med, 1.0) and count >= self.min and count and uniq / count >= self.uniq:
                strength = min(1.0, (count - mean) / max(std * 6, 6.0))
                hype = min(1.0, b.get("hype", 0) / max(3.0, count * 0.3))
                score = 10 * (0.5 * strength + 0.2 * (uniq / count) + 0.15 * hype + 0.15 * min(1.0, max(0.0, audio_z) / 3.0)) + (1.0 if audio_z >= 1.5 else 0.0)
                fire = {"kind": "chat", "count": count, "unique": uniq, "mean": round(mean, 1), "std": round(std, 1), "top": b.get("top", []),
                        "samples": b.get("samples", []), "audio_z": round(audio_z, 1), "score": round(min(10.0, score), 1)}
                self.until = t + self.cool
        self.hist.append(count)
        return fire

    def push_audio(self, t: float, level_db: float) -> dict | None:
        """For streams with no chat reader: a loudness z-score of audio_z or more held for 2 seconds is a moment."""
        self.loud.append(level_db)
        if len(self.loud) < 60:
            return None
        base = list(self.loud)[:-1]
        sd = statistics.pstdev(base) or 1.0
        z = (level_db - statistics.fmean(base)) / sd
        self.run = self.run + 1 if z >= self.audio_z else 0
        if self.run >= 2 and t >= self.until:
            self.until = t + self.cool
            self.run = 0
            return {"kind": "audio", "count": 0, "unique": 0, "audio_z": round(z, 1), "top": [], "samples": [], "score": round(min(10.0, 4 + z), 1)}
        return None


def audio_z_of(levels: list[float], history: list[float]) -> float:
    """z-score of the loudest 2 seconds of `levels` against the earlier loudness `history`."""
    if len(history) < 20 or len(levels) < 2:
        return 0.0
    sd = statistics.pstdev(history) or 1.0
    best = max(min(levels[i], levels[i + 1]) for i in range(len(levels) - 1))
    return (best - statistics.fmean(history)) / sd


def window(seg_start: float, spike_rel: float, pre: float, post: float, session_len: float) -> tuple[int, int]:
    """Indexes (first, last inclusive) of the 10-second pieces to join: from `pre` s before the spike to `post` s after it."""
    a = max(0.0, spike_rel - pre)
    b = min(session_len, spike_rel + post)
    return int(a // SEGMENT), max(int(a // SEGMENT), int((b - 0.001) // SEGMENT))


# ---------- chat readers ----------
class TwitchChat(threading.Thread):
    def __init__(self, channel: str, counter: ChatCounter, stop: threading.Event, log_path: Path | None = None) -> None:
        super().__init__(daemon=True, name=f"live-chat-{channel}")
        self.channel, self.counter, self.stop_ev, self.log_path = channel.lower(), counter, stop, log_path
        self.connected = False

    def run(self) -> None:
        back = 2.0
        while not self.stop_ev.is_set():
            try:
                raw = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=15)
                s = ssl.create_default_context().wrap_socket(raw, server_hostname="irc.chat.twitch.tv")
                s.settimeout(30)
                import random
                s.sendall(f"NICK justinfan{random.randint(10000, 99999)}\r\nJOIN #{self.channel}\r\n".encode())
                buf = ""
                self.connected = True
                back = 2.0
                while not self.stop_ev.is_set():
                    try:
                        data = s.recv(4096).decode("utf-8", "replace")
                    except socket.timeout:
                        continue
                    if not data:
                        break
                    buf += data
                    while "\r\n" in buf:
                        line, buf = buf.split("\r\n", 1)
                        if line.startswith("PING"):
                            s.sendall(b"PONG :tmi.twitch.tv\r\n")
                            continue
                        m = parse_irc(line)
                        if m:
                            self.counter.add(*m)
            except Exception:  # noqa: BLE001 - reconnect with backoff
                pass
            self.connected = False
            self.stop_ev.wait(back)
            back = min(60.0, back * 2)


# ---------- recording ----------
def tools() -> dict:
    return {"streamlink": bool(shutil.which("streamlink")), "ffmpeg": bool(shutil.which("ffmpeg"))}


def is_live(url: str) -> bool:
    try:
        r = subprocess.run(["streamlink", "--json", url], capture_output=True, text=True, timeout=45)
        j = json.loads(r.stdout or "{}")
        return bool(j.get("streams")) and not j.get("error")
    except Exception:  # noqa: BLE001
        return False


def join_pieces(files: list[Path], out: Path) -> Path:
    """Join recorded .ts pieces into one mp4 without re-encoding."""
    lst = out.with_suffix(".txt")
    lst.write_text("".join(f"file '{f.as_posix()}'\n" for f in files), "utf-8")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-nostdin", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-bsf:a", "aac_adtstoasc", str(out)],
                       capture_output=True, text=True, timeout=600)
    lst.unlink(missing_ok=True)
    if r.returncode != 0 or not out.is_file():
        raise RuntimeError("could not join the recorded pieces: " + (r.stderr.strip().splitlines() or ["unknown"])[-1][:160])
    return out


def piece_loudness(f: Path) -> list[float]:
    try:
        from . import pick
        return pick.loudness(str(f))
    except Exception:  # noqa: BLE001
        return []


# ---------- turning a spike into a job ----------
def make_job(streamer: dict, files: list[Path], moment: dict, settings: dict) -> str:
    from . import pipeline
    opts = pipeline.build_opts({"count": 1, "min_seconds": 20, "max_seconds": 60, "preset": settings.get("preset") or "", "layout": "auto"})
    title = f"{streamer['handle']} live moment {time.strftime('%d %b %H:%M')}"
    job = pipeline.new_job(opts, {"kind": "upload", "name": title, "live": {"platform": streamer["platform"], "handle": streamer["handle"], **{k: moment.get(k) for k in ("kind", "count", "unique", "score", "audio_z", "top", "samples")}}})
    join_pieces(files, store.jdir(job["id"]) / "source.mp4")
    perm = rights.permission_for("ask", bool(streamer.get("permission")))         # no confirmed permission = the clip is made but cannot be posted
    store.update(job["id"], lambda j: j.__setitem__("permission", perm))
    pipeline.start(job["id"])
    return job["id"]


# ---------- the watcher ----------
class Watch(threading.Thread):
    def __init__(self, streamer: dict, settings: dict, stop: threading.Event, board: dict) -> None:
        super().__init__(daemon=True, name=f"live-{streamer['id']}")
        self.s, self.cfg, self.stop_ev, self.board = streamer, settings, stop, board
        self.url = url_for(streamer)

    def say(self, **kw: Any) -> None:
        with LOCK:
            self.board.setdefault(self.s["id"], {"id": self.s["id"], "state": "offline"}).update(kw)

    def run(self) -> None:
        self.say(state="offline", error=None)
        while not self.stop_ev.is_set():
            try:
                if is_live(self.url):
                    self.record()
                    self.say(state="offline")
                else:
                    self.say(state="offline")
            except Exception as e:  # noqa: BLE001 - one stream failing never stops the others
                self.say(state="error", error=str(e)[:160])
            self.stop_ev.wait(60)

    def record(self) -> None:
        sess = _dir() / "sessions" / self.s["id"] / time.strftime("%Y%m%d-%H%M%S")
        sess.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        sl = subprocess.Popen(["streamlink", "-O", "--twitch-low-latency", self.url, "720p60,720p,best"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-nostdin", "-i", "-", "-map", "0:v:0", "-map", "0:a:0", "-c", "copy", "-f", "segment", "-segment_time", str(SEGMENT),
                               "-reset_timestamps", "1", str(sess / "%06d.ts")], stdin=sl.stdout, stderr=subprocess.DEVNULL)
        counter, chat = ChatCounter(), None
        det = Detector(self.s["min_messages"], **self.cfg)
        if self.s["platform"] == "twitch":
            chat = TwitchChat(self.s["handle"], counter, self.stop_ev)
            chat.start()
        self.say(state="live", since=time.strftime("%H:%M"), session=str(sess), error=None)
        pending: list[tuple[float, dict]] = []
        done_pieces, last_t, hist = 0, t0, []
        fired: list[float] = []
        try:
            while not self.stop_ev.is_set() and ff.poll() is None:
                self.stop_ev.wait(BUCKET)
                now = time.time()
                rel = now - t0
                b = counter.flush()
                self.say(rate=b["count"], chat=bool(chat and chat.connected))
                pieces = sorted(sess.glob("*.ts"))
                audio_z = 0.0
                if len(pieces) - 1 > done_pieces:                           # a finished piece (the last one is still being written)
                    lv = piece_loudness(pieces[done_pieces])
                    if lv:
                        audio_z = audio_z_of(lv, hist)
                        hist.extend(lv)
                        hist[:] = hist[-600:]
                        if not (chat and chat.connected):
                            m = det.push_audio(rel, max(lv))
                            if m:
                                pending.append((rel, m))
                    done_pieces += 1
                if chat and chat.connected:
                    m = det.push(rel, b, audio_z)
                    if m:
                        pending.append((rel, m))
                for item in list(pending):                                  # wait `post` seconds after the spike so the payoff is recorded
                    srel, m = item
                    if rel >= srel + float(self.cfg["post"]) + SEGMENT:
                        pending.remove(item)
                        recent = [x for x in fired if now - x < 3600]
                        if len(recent) >= int(self.cfg["per_hour"]):
                            self.say(note="Skipped a moment: the per-hour limit for this streamer is reached.")
                            continue
                        fired.append(now)
                        self.cut(sess, srel, m, rel)
                self.cleanup(sess)
        finally:
            for p in (ff, sl):
                try:
                    p.kill()
                except Exception:  # noqa: BLE001
                    pass

    def cut(self, sess: Path, srel: float, moment: dict, session_len: float) -> None:
        a, b = window(0, srel, float(self.cfg["pre"]), float(self.cfg["post"]), session_len)
        files = [sess / f"{i:06d}.ts" for i in range(a, b + 1) if (sess / f"{i:06d}.ts").is_file()]
        if len(files) < 3:
            return
        entry = {"id": store.new_id(), "streamer": self.s["id"], "at": store.now(), "score": moment["score"], "kind": moment["kind"], "count": moment["count"],
                 "unique": moment["unique"], "top": moment["top"], "samples": moment["samples"], "audio_z": moment["audio_z"], "job": None, "error": None}
        self.say(last=entry["at"], moments=self.board.get(self.s["id"], {}).get("moments", 0) + 1)

        def work() -> None:                                            # off the recording loop: processing can take minutes and chat must keep being counted
            try:
                entry["job"] = JOBS.submit(self.s, files, moment, self.cfg)
            except Exception as e:  # noqa: BLE001
                entry["error"] = str(e)[:200]
            log_moment(entry)
        threading.Thread(target=work, daemon=True, name="live-cut").start()

    def cleanup(self, sess: Path) -> None:
        keep = float(self.cfg["keep_hours"]) * 3600
        for f in sess.glob("*.ts"):
            try:
                if time.time() - f.stat().st_mtime > keep:
                    f.unlink()
            except OSError:
                pass


class _Jobs:
    """Cuts and processing happen a couple at a time, so ten streamers spiking together do not melt the computer."""

    def __init__(self, n: int = 2) -> None:
        self.sem = threading.Semaphore(n)

    def submit(self, streamer: dict, files: list[Path], moment: dict, cfg: dict) -> str:
        from . import pipeline
        with self.sem:
            jid = make_job(streamer, files, moment, cfg)
            for _ in range(900):                                           # wait for this job to finish before the next starts (max 15 min)
                if not pipeline.busy(jid):
                    break
                time.sleep(1)
        return jid


JOBS = _Jobs()


def log_moment(e: dict) -> None:
    with LOCK:
        p = _dir() / "moments.jsonl"
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def moments(limit: int = 50) -> list[dict]:
    p = _dir() / "moments.jsonl"
    if not p.is_file():
        return []
    rows = []
    for line in p.read_text("utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows[::-1]


# ---------- start / stop ----------
_watchers: list[Watch] = []
_stop = threading.Event()
BOARD: dict[str, dict] = {}


def start() -> dict:
    with LOCK:
        d = load()
        stop()
        _stop.clear()
        for s in d["streamers"]:
            if s.get("on", True):
                w = Watch(s, d["settings"], _stop, BOARD)
                _watchers.append(w)
                w.start()
        d["running"] = True
        _save(d)
    return state()


def stop() -> None:
    _stop.set()
    _watchers.clear()
    with LOCK:
        d = load()
        if d["running"]:
            d["running"] = False
            _save(d)


def resume() -> None:
    """After a restart: pick the watching up again if it was on."""
    if load().get("running"):
        start()


def state() -> dict:
    d = load()
    with LOCK:
        board = {k: dict(v) for k, v in BOARD.items()}
    rows = []
    for s in d["streamers"]:
        rows.append({**s, "url": url_for(s), **{k: v for k, v in board.get(s["id"], {}).items() if k != "id"}})
    return {"running": bool(d["running"]) and not _stop.is_set(), "streamers": rows, "settings": d["settings"], "tools": tools(), "moments": moments()}
