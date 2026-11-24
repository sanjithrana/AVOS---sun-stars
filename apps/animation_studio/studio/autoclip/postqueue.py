"""The YouTube tab's engine: a queue of posts (one video to one channel each), a time planner, a worker and the numbers.

A post is {id, src, channel, title, description, privacy, at, status, ...}
  src      {"jid","n"} a clip from the Library, or {"upload": id} a video you added here
  at       when to post (UTC); None = as soon as the worker next ticks
  status   queued -> posting -> posted | failed | cancelled
Safety, same as Autopilot: a post is marked 'posting' BEFORE the upload starts so a restart can never post it twice, a broken login holds the
channel's posts instead of looping, and a clip with no permission never leaves the building."""
from __future__ import annotations

import re

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import cut, rights, social, store, youtube

LOCK = threading.RLock()
FILE = lambda: store.ROOT / "postqueue.json"      # noqa: E731 - looked up late so tests can point ROOT elsewhere
UPLOADS = lambda: store.ROOT / "uploads"          # noqa: E731
PLAN = {"per_day": 3, "min_gap_minutes": 120, "hours": [9, 21], "privacy": "private", "ahead_hours": 0}
AHEAD_OK = ("youtube", "facebook")      # these two can publish a video later by themselves; Instagram and TikTok cannot
_last_stats = 0.0


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse(t: str | None) -> datetime | None:
    try:
        d = datetime.fromisoformat(t) if t else None
        return d if d is None or d.tzinfo else (d.replace(tzinfo=timezone.utc) if d else None)
    except ValueError:
        return None


def _load() -> dict:
    d = store._read(FILE(), None) or {}
    d.setdefault("posts", [])
    d["plan"] = {**PLAN, **(d.get("plan") or {})}
    d["plan"].setdefault("channels", {})
    return d


def plan_for(d: dict, ch: str) -> dict:
    """The default plan with this channel's own settings on top."""
    base = {k: v for k, v in d["plan"].items() if k != "channels"}
    return {**base, **(d["plan"].get("channels") or {}).get(ch, {})}


def platform_of(ch: str) -> str:
    return ch.split(":", 1)[0] if social.is_social(ch) else "youtube"


def _save(d: dict) -> None:
    store._write(FILE(), d)


def plan() -> dict:
    return _load()["plan"]


def set_plan(p: dict, channel: str | None = None) -> dict:
    """The default plan, or one channel's own settings (channel=id; reset=True puts it back to the default)."""
    with LOCK:
        d = _load()
        if channel and p.get("reset"):
            (d["plan"]["channels"] or {}).pop(channel, None)
            _save(d)
            return plan_for(d, channel)
        cur = d["plan"] if not channel else d["plan"]["channels"].setdefault(channel, {})
        try:
            if "per_day" in p:
                cur["per_day"] = max(1, min(20, int(p["per_day"])))
            if "min_gap_minutes" in p:
                cur["min_gap_minutes"] = max(10, min(1440, int(p["min_gap_minutes"])))
            if "hours" in p:
                a, b = int(p["hours"][0]), int(p["hours"][1])
                if not (0 <= a <= 23 and 0 <= b <= 24) or a == b:
                    raise ValueError("hours")
                cur["hours"] = [a, b]
            if "ahead_hours" in p:
                cur["ahead_hours"] = max(0, min(720, int(p["ahead_hours"])))
        except (TypeError, ValueError, IndexError):
            raise ValueError("Those posting times are not valid.")
        if p.get("privacy") in ("private", "unlisted", "public"):
            cur["privacy"] = p["privacy"]
        _save(d)
        return plan_for(d, channel) if channel else cur


# ---------- the planner ----------
def slots(taken: list[datetime], n: int, start: datetime, pl: dict, tz_min: int) -> list[datetime]:
    """The next `n` posting times for one channel. Each day's window (e.g. 9 to 21) is cut into per_day equal parts and one post goes in the middle of
    each, skipping times that are in the past, closer than the minimum gap to another post, or on a day that already has per_day posts."""
    a, b = pl["hours"]
    end_h = b if b > a else b + 24
    win = (end_h - a) * 60
    per = max(1, int(pl["per_day"]))
    gap = timedelta(minutes=int(pl["min_gap_minutes"]))
    off = timedelta(minutes=tz_min)
    chosen: list[datetime] = []
    day0 = (start + off).replace(hour=0, minute=0, second=0, microsecond=0)
    for k in range(-1, 120):
        day = day0 + timedelta(days=k)
        for i in range(per):
            local = day + timedelta(hours=a, minutes=int((i + 0.5) * win / per))
            t = local - off
            if t < start + timedelta(minutes=2):
                continue
            allt = taken + chosen
            same_day = sum(1 for x in allt if (x + off).date() == local.date())
            if same_day >= per or any(abs(x - t) < gap for x in allt):
                continue
            chosen.append(t)
            if len(chosen) == n:
                return sorted(chosen)
    return sorted(chosen)


# ---------- what can be posted ----------
def _allowed(job: dict, st: dict) -> bool:
    perm = job.get("permission")
    return rights.can_post(job) if perm else bool(st.get("rights_ack"))


def library() -> list[dict]:
    """Every finished, unposted clip from Auto Clip, newest first: this is what the tab lets you tick."""
    queued = {(p["src"].get("jid"), p["src"].get("n")) for p in _load()["posts"] if p["status"] in ("queued", "posting") and p["src"].get("jid")}
    st = store.settings()
    out = []
    for j in store.listing():
        job = store.load(j["id"])
        for c in job.get("clips") or []:
            if c.get("status") != "ready" or not c.get("file") or c.get("youtube_id"):
                continue
            out.append({"jid": job["id"], "n": c["n"], "title": c.get("title") or "", "job_title": job.get("title") or "", "duration": c.get("duration"),
                        "thumb": c.get("cover") or c.get("thumb"), "permission": job.get("permission") or ("granted" if st.get("rights_ack") else "unconfirmed"),
                        "allowed": _allowed(job, st), "queued": (job["id"], c["n"]) in queued, "created": job.get("createdAt")})
    return out


def uploads() -> list[dict]:
    d = UPLOADS()
    out = []
    for m in sorted(d.glob("*.json"), reverse=True) if d.is_dir() else []:
        x = store._read(m, None)
        if x and (d / f"{x['id']}.mp4").is_file():
            out.append(x)
    return out


def add_upload(name: str, data_path: Path, ack: bool) -> dict:
    """File already saved at data_path by the route; make its record and a thumbnail."""
    uid = store.new_id()
    d = UPLOADS()
    d.mkdir(parents=True, exist_ok=True)
    dst = d / f"{uid}.mp4"
    data_path.replace(dst)
    title = Path(name).stem.replace("_", " ").replace("-", " ").strip()[:95] or "My video"
    try:
        cover = cut.cover(str(dst), str(d / f"{uid}.jpg"), "")
    except Exception:  # noqa: BLE001
        cover = False
    rec = {"id": uid, "title": title, "ack": bool(ack), "thumb": bool(cover), "created": store.now()}
    store._write(d / f"{uid}.json", rec)
    return rec


def _src_path(src: dict) -> tuple[Path | None, Path | None, str]:
    """(video file, cover image, default title)"""
    if src.get("upload"):
        u = store._read(UPLOADS() / f"{src['upload']}.json", None) or {}
        cov = UPLOADS() / f"{src['upload']}.jpg"
        return UPLOADS() / f"{src['upload']}.mp4", (cov if cov.is_file() else None), u.get("title") or "My video"
    job = store.load(src["jid"])
    c = next((x for x in job["clips"] if x["n"] == src["n"]), None)
    if not c:
        return None, None, ""
    cv = c.get("cover") or c.get("thumb")
    return store.jdir(src["jid"]) / c["file"], (store.jdir(src["jid"]) / cv if cv else None), c.get("title") or ""


# ---------- making posts ----------
def add(items: list[dict], channels: list[str], mode: str, at: str | None = None, privacy: str | None = None, spread: bool = True, gap_min: float = 3.0, gap_max: float = 5.0, gap_hours: float = 0.0) -> list[dict]:
    """items [{jid,n}|{jid,all:true}|{upload}] x channels. mode: now | drip (one by one from now, 3-5 min apart) | every (the first now, then one every `gap_hours` hours) | schedule (one time `at`, then spaced by the minimum gap) | auto (planner picks the times)."""
    if not items or not channels:
        raise ValueError("Pick at least one video and one channel.")
    known = {c["id"]: c for c in youtube.channels() + social.accounts()}
    items = _expand(items)
    for c in channels:
        if c not in known:
            raise ValueError("That channel is not connected.")
    st = store.settings()
    with LOCK:
        d = _load()
        pl = d["plan"]
        made = []
        for it in items:
            src = {"upload": it["upload"]} if it.get("upload") else {"jid": str(it.get("jid") or ""), "n": int(it.get("n") or 0)}
            if src.get("upload"):
                u = store._read(UPLOADS() / f"{src['upload']}.json", None)
                if not u:
                    raise ValueError("That upload is gone.")
                if not (u.get("ack") or st.get("rights_ack")):
                    raise ValueError("Confirm you own this video or have permission before queueing it.")
            else:
                if not store.exists(src["jid"]):
                    raise ValueError("That clip is gone.")
                job = store.load(src["jid"])
                if not any(x["n"] == src["n"] and x.get("file") for x in job["clips"]):
                    raise ValueError("That clip is not finished.")
                if not _allowed(job, st):
                    raise ValueError(f"“{job['title']}” has no permission yet. Open it in Auto Clip and confirm you may clip it first.")
            title = _src_path(src)[2]
            for ch in channels:
                if any(p["status"] in ("queued", "posting") and p["channel"] == ch and p["src"] == src for p in d["posts"]):
                    continue                                     # never queue the same video to the same channel twice
                made.append({"id": store.new_id(), "src": src, "channel": ch, "title": title[:95], "description": "", "privacy": privacy or plan_for(d, ch)["privacy"],
                             "at": None, "status": "queued", "created": store.now(), "mode": mode})
        if mode == "schedule":
            t0 = parse(at)
            if not t0:
                raise ValueError("Pick a date and time.")
            seen: dict[str, int] = {}
            for p in made:
                k = seen.get(p["channel"], 0)
                gap = timedelta(minutes=plan_for(d, p["channel"])["min_gap_minutes"]) if spread else timedelta(0)
                p["at"] = iso(t0 + gap * k)
                seen[p["channel"]] = k + 1
        elif mode == "every":
            if not 0.05 <= float(gap_hours) <= 72:
                raise ValueError("Pick a gap between 3 minutes and 72 hours.")
            import random
            for ch in channels:
                t = now()
                for p in [p for p in made if p["channel"] == ch]:
                    p["at"] = iso(t)
                    t = t + timedelta(hours=float(gap_hours)) + timedelta(minutes=random.uniform(0, min(5.0, float(gap_hours) * 6)))
        elif mode == "drip":
            for ch in channels:
                _drip_times([p for p in made if p["channel"] == ch], now(), gap_min, gap_max)
        elif mode == "auto":
            for ch in channels:
                mine = [p for p in made if p["channel"] == ch]
                taken = [x for x in (parse(p.get("at")) for p in d["posts"] if p["channel"] == ch and p["status"] in ("queued", "posting")) if x]
                taken += [x for x in (parse(p.get("posted_at")) for p in d["posts"] if p["channel"] == ch and p["status"] == "posted") if x and now() - x < timedelta(days=2)]
                for p, t in zip(mine, slots(taken, len(mine), now(), plan_for(d, ch), st["tz_offset_minutes"])):
                    p["at"] = iso(t)
        d["posts"] = made + d["posts"]
        _save(d)
        return made


def _expand(items: list[dict]) -> list[dict]:
    """{jid, all: true} becomes one item per finished clip of that job, in clip order (the 'add all in a row' button)."""
    out: list[dict] = []
    for it in items:
        if it.get("all") and it.get("jid") and store.exists(str(it["jid"])):
            job = store.load(str(it["jid"]))
            out += [{"jid": str(it["jid"]), "n": c["n"]} for c in sorted(job["clips"], key=lambda c: c["n"]) if c.get("file")]
        else:
            out.append(it)
    return out


def _drip_times(posts: list[dict], start: datetime, gap_min: float = 3.0, gap_max: float = 5.0, rng: Any = None) -> None:
    """The first post goes now, each next one 3 to 5 minutes after the one before (random, so it does not look like a robot)."""
    import random
    r = rng or random
    lo, hi = max(0.5, float(gap_min)), max(float(gap_min), float(gap_max))
    t = start
    for p in posts:
        p["at"] = iso(t)
        t = t + timedelta(minutes=r.uniform(lo, hi))


def drip(channel: str | None = None, gap_min: float = 3.0, gap_max: float = 5.0, rng: Any = None) -> int:
    """Re-time every waiting post (of one channel, or all) so they go out one by one starting now. Returns how many were set."""
    n = 0
    with LOCK:
        d = _load()
        chs = [channel] if channel else sorted({p["channel"] for p in d["posts"]})
        for ch in chs:
            mine = [p for p in d["posts"] if p["channel"] == ch and p["status"] == "queued" and not p.get("hold")]
            mine.sort(key=lambda p: (p.get("at") or p["created"]))
            _drip_times(mine, now(), gap_min, gap_max, rng)
            n += len(mine)
        _save(d)
    return n


def set_privacy(privacy: str, channel: str | None = None) -> int:
    """Visibility for every waiting post (of one channel, or all). Also becomes that channel's default for the posts you add next."""
    if privacy not in ("private", "unlisted", "public"):
        raise ValueError("Pick private, unlisted or public.")
    n = 0
    with LOCK:
        d = _load()
        for p in d["posts"]:
            if p["status"] in ("queued", "failed") and (not channel or p["channel"] == channel):
                p["privacy"] = privacy
                n += 1
        _save(d)
    return n


def edit(pid: str, b: dict) -> dict:
    with LOCK:
        d = _load()
        p = next((x for x in d["posts"] if x["id"] == pid), None)
        if not p:
            raise KeyError(pid)
        if p["status"] not in ("queued", "failed"):
            raise ValueError("Only waiting posts can be changed.")
        if "title" in b:
            p["title"] = youtube.clean_text(b["title"], 95) or p["title"]
        if "description" in b:
            p["description"] = youtube.clean_text(b["description"], 4800)
        if b.get("privacy") in ("private", "unlisted", "public"):
            p["privacy"] = b["privacy"]
        if "at" in b:
            t = parse(b["at"]) if b["at"] else None
            p["at"] = iso(t) if t else None
        _save(d)
        return p


def cancel(pid: str) -> bool:
    with LOCK:
        d = _load()
        p = next((x for x in d["posts"] if x["id"] == pid), None)
        if not p or p["status"] == "posting":
            return False
        if p["status"] == "posted":
            return False
        p["status"] = "cancelled"
        _save(d)
        return True


def retry(pid: str) -> bool:
    with LOCK:
        d = _load()
        p = next((x for x in d["posts"] if x["id"] == pid), None)
        if not p or p["status"] not in ("failed", "cancelled"):
            return False
        p.update(status="queued", error=None, at=None)
        _save(d)
        return True


def clear_done() -> int:
    with LOCK:
        d = _load()
        n = len(d["posts"])
        d["posts"] = [p for p in d["posts"] if p["status"] in ("queued", "posting", "posted")]
        _save(d)
        return n - len(d["posts"])


# ---------- the worker ----------
def _patch(pid: str, **kw: Any) -> None:
    with LOCK:
        d = _load()
        for p in d["posts"]:
            if p["id"] == pid:
                p.update(kw)
        _save(d)


LIMIT = re.compile(r"exceeded the number of videos|uploadLimitExceeded|upload limit", re.I)
LIMIT_NOTE = ("YouTube's daily upload limit for this channel is used up, so this waits 24 hours and goes out on its own. "
              "To raise the limit, verify the channel with your phone at youtube.com/verify, and post fewer videos a day until the channel is older.")


def _limit_wait(channel: str, t: datetime) -> None:
    """Every waiting post of this channel moves to at least 24 hours from now, spaced out again, with the reason on each."""
    with LOCK:
        d = _load()
        gap = timedelta(minutes=int(plan_for(d, channel).get("min_gap_minutes") or 60))
        nxt = t + timedelta(hours=24, minutes=5)
        mine = sorted([p for p in d["posts"] if p["channel"] == channel and p["status"] in ("queued", "posting") or
                       (p["channel"] == channel and p["status"] == "failed" and LIMIT.search(p.get("error") or ""))], key=lambda p: (p.get("at") or p["created"]))
        for p in mine:
            at = parse(p.get("at"))
            when = max(nxt, at) if at else nxt
            p.update(status="queued", at=iso(when), error=LIMIT_NOTE, started=None)
            nxt = when + gap
        _save(d)


def tick(uploader: Callable[..., str] | None = None, thumber: Callable[..., Any] | None = None, at: datetime | None = None, only: str | None = None) -> str | None:
    """One action: post the oldest due post (or just the post `only`). Returns what it did, or None."""
    up = uploader or youtube.upload
    th = thumber or youtube.set_thumbnail
    t = at or now()
    with LOCK:
        stuck = {p["channel"] for p in _load()["posts"] if p["status"] == "failed" and LIMIT.search(p.get("error") or "")}
    for ch in stuck:                                    # posts that failed on the daily limit before this fix: they wait a day instead
        _limit_wait(ch, t)
    with LOCK:
        d = _load()
        changed = False
        for p in d["posts"]:
            if p["status"] == "posting" and (parse(p.get("started")) or t) < t - timedelta(hours=2):
                p.update(status="failed", error="Interrupted. Check the channel before you retry so it is not posted twice.")
                changed = True
        if changed:
            _save(d)
        blocked = {p["channel"] for p in d["posts"] if p["status"] == "posting"}
        def lead(p: dict) -> timedelta:              # how early a post may be uploaded so the platform itself publishes it on time
            if p.get("privacy") != "public" or platform_of(p["channel"]) not in AHEAD_OK:
                return timedelta(0)
            return timedelta(hours=int(plan_for(d, p["channel"]).get("ahead_hours") or 0))
        due = [p for p in d["posts"] if p["status"] == "queued" and p["channel"] not in blocked and (parse(p.get("at")) or t) - lead(p) <= t and not p.get("hold") and (not only or p["id"] == only)]
        due.sort(key=lambda p: (p.get("at") or p["created"]))
        if not due:
            return None
        p = due[0]
        p.update(status="posting", started=iso(t), error=None)
        _save(d)
    pid = p["id"]
    try:
        vf, cov, _ = _src_path(p["src"])
        if not vf or not vf.is_file():
            raise RuntimeError("The video file is missing.")
        if p["src"].get("jid") and not _allowed(store.load(p["src"]["jid"]), store.settings()):
            raise RuntimeError("No permission on this clip yet.")
        desc, tags, ttl = p.get("description") or "", [], p["title"]
        try:
            from . import coach, meta
            src = p["src"]
            if src.get("jid"):
                job = store.load(src["jid"])
                c = next((x for x in job["clips"] if x["n"] == src["n"]), None)
                ttl = meta.mention_title(p["title"], job, c)
                if c:
                    desc, tags = meta.build({**c, "description": p.get("description") or c.get("description") or ""}, job, coach.tags_for_posting())
            else:
                desc, tags = meta.build({"title": p["title"], "description": desc}, None, coach.tags_for_posting())
        except Exception:  # noqa: BLE001 - hashtags are never worth losing a post
            pass
        other = social.is_social(p["channel"]) and uploader is None
        at_t = parse(p.get("at"))
        later = at_t if (at_t and at_t > t + timedelta(minutes=11) and p.get("privacy") == "public" and platform_of(p["channel"]) in AHEAD_OK) else None
        if other:
            res = social.publish(p["channel"], str(vf), ttl, desc, p.get("privacy") or "private", tags, later.timestamp() if later else None)
            vid = None
        elif later:
            vid = up(p["channel"], str(vf), ttl, desc, p.get("privacy") or "private", tags, publish_at=iso(later))
        else:
            vid = up(p["channel"], str(vf), ttl, desc, p.get("privacy") or "private", tags)
    except youtube.NeedsLogin as e:
        _patch(pid, status="queued", error=str(e)[:300], hold=True)
        _hold_channel(p["channel"], str(e))
        return f"login:{p['channel']}"
    except Exception as e:  # noqa: BLE001
        if LIMIT.search(str(e)):                                   # YouTube's daily upload limit: wait a day, never a failure
            _limit_wait(p["channel"], t)
            return f"limit:{p['channel']}"
        _patch(pid, status="failed", error=str(e)[:300], attempts=int(p.get("attempts", 0)) + 1)
        return f"failed:{pid}"
    if other:                                                     # Instagram / Facebook / TikTok: no YouTube id, cover or numbers
        _patch(pid, status="posted", remote_id=res["id"], remote_url=res.get("url"), posted_at=iso(t), thumb_status="n/a", error=None, scheduled_for=iso(later) if later else None)
        if p["src"].get("jid"):
            def g(j: dict) -> None:
                for x in j["clips"]:
                    if x["n"] == p["src"]["n"]:
                        x.setdefault("posted_other", []).append({"channel": p["channel"], "at": iso(t), "id": res["id"]})
            try:
                store.update(p["src"]["jid"], g)
            except Exception:  # noqa: BLE001
                pass
        return f"posted:{pid}"
    thumb = "none"
    if cov and cov.is_file():
        try:
            th(p["channel"], vid, str(cov))
            thumb = "set"
        except Exception as e:  # noqa: BLE001 - the video is up; a refused cover is only noted
            thumb = "not accepted: " + str(e)[:120]
    note = None
    if p.get("privacy") == "public" and not later and youtube.LAST_PRIVACY.get(str(vid)) == "private":
        note = ("YouTube kept this video private even though you chose Public. That happens when the Google Cloud app used for posting has not passed YouTube's API audit "
                "(videos uploaded by unverified apps are locked to private). Fix: apply for the audit at support.google.com/youtube/contact/yt_api_form, or open the video in YouTube Studio and set it to Public by hand.")
    _patch(pid, status="posted", youtube_id=vid, posted_at=iso(t), thumb_status=thumb, error=None, scheduled_for=iso(later) if later else None, note=note)
    if p["src"].get("jid"):                                       # the Library clip shows as posted too
        def f(j: dict) -> None:
            for x in j["clips"]:
                if x["n"] == p["src"]["n"]:
                    x.update(status="posted", youtube_id=vid, posted_at=iso(t), channel=p["channel"], privacy=p["privacy"])
        try:
            store.update(p["src"]["jid"], f)
            from . import experiments
            experiments.begin(p["src"]["jid"], p["src"]["n"])
        except Exception:  # noqa: BLE001
            pass
    return f"posted:{pid}"


def _hold_channel(ch: str, why: str) -> None:
    with LOCK:
        d = _load()
        for p in d["posts"]:
            if p["channel"] == ch and p["status"] == "queued":
                p["hold"] = True
                p["error"] = why[:300]
        _save(d)


def release(ch: str) -> int:
    """After you sign in again: let a held channel's posts go."""
    with LOCK:
        d = _load()
        n = 0
        for p in d["posts"]:
            if p["channel"] == ch and p.get("hold"):
                p.pop("hold")
                p["error"] = None
                n += 1
        _save(d)
        return n


# ---------- monitoring ----------
def refresh(force: bool = False, reader: Callable[[str, list[str]], dict] | None = None) -> int:
    global _last_stats
    import time
    if not force and time.time() - _last_stats < 600:
        return 0
    _last_stats = time.time()
    rd = reader or youtube.stats
    with LOCK:
        d = _load()
    by: dict[str, list[dict]] = {}
    for p in d["posts"]:
        if p["status"] == "posted" and p.get("youtube_id"):
            by.setdefault(p["channel"], []).append(p)
    n = 0
    for ch, ps in by.items():
        try:
            data = rd(ch, [p["youtube_id"] for p in ps])
        except Exception:  # noqa: BLE001
            continue
        for p in ps:
            s = data.get(p["youtube_id"])
            _patch(p["id"], stats=(s | {"at": store.now()}) if s else {"removed": True, "at": store.now()})
            n += 1
    return n


def overview() -> dict:
    d = _load()
    chans = {c["id"]: c for c in youtube.channels() + social.accounts()}
    summ: dict[str, dict] = {c: {"id": c, "title": chans[c]["title"], "thumb": chans[c].get("thumb"), "needs_login": chans[c].get("needs_login"), "subs": chans[c].get("subs"), "platform": chans[c].get("platform", "youtube"), "can_schedule": chans[c].get("platform", "youtube") in AHEAD_OK, "plan": plan_for(d, c), "own_plan": c in (d["plan"].get("channels") or {}),
                                "queued": 0, "posted": 0, "failed": 0, "views": 0, "likes": 0, "comments": 0, "next": None} for c in chans}
    t = now()
    for p in d["posts"]:
        s = summ.get(p["channel"])
        if not s:
            continue
        if p["status"] == "queued":
            s["queued"] += 1
            at = p.get("at")
            if at and (s["next"] is None or at < s["next"]):
                s["next"] = at
        elif p["status"] == "posted":
            s["posted"] += 1
            st = p.get("stats") or {}
            s["views"] += int(st.get("views") or 0)
            s["likes"] += int(st.get("likes") or 0)
            s["comments"] += int(st.get("comments") or 0)
        elif p["status"] == "failed":
            s["failed"] += 1
    posts = [dict(p, url=(f"https://youtube.com/shorts/{p['youtube_id']}" if p.get("youtube_id") else p.get("remote_url")), channel_title=(chans.get(p["channel"]) or {}).get("title", "(removed)"),
                  thumb=_thumb(p)) for p in d["posts"]]
    return {"plan": d["plan"], "posts": posts[:300], "channels": list(summ.values()), "now": iso(t)}


def _thumb(p: dict) -> dict | None:
    s = p["src"]
    if s.get("upload"):
        return {"upload": s["upload"]}
    try:
        c = next(x for x in store.load(s["jid"])["clips"] if x["n"] == s["n"])
    except Exception:  # noqa: BLE001
        return None
    cv = c.get("cover") or c.get("thumb")
    return {"jid": s["jid"], "name": cv} if cv else None
