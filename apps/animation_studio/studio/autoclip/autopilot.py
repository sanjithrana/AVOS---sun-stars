"""Autopilot: the part that posts with nobody pressing anything. A small loop, one tick a minute, one action per tick.

It posts a clip only when ALL of these hold (each is a setting you can see in the tab):
  - Autopilot is on and not paused, and you have said you own the video or have permission to clip it
  - the clip is approved (or "review first" is off, which is fully automatic)
  - fewer than the daily cap have gone out in the last 24 hours, and the minimum gap since the last one has passed
  - it is inside your posting hours, and the clip's own schedule time (if you set one) has come
  - the YouTube login still works. If Google stops accepting it, posting PAUSES and the tab says why: it never loops on a broken login.
A crash while uploading marks that clip 'posting' first, so a restart can never post it twice."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import coach, comments, experiments, meta, pipeline, postqueue, retention, rights, store, youtube

_loop: threading.Thread | None = None
_stop = threading.Event()
TICK = 60
_last_stats = 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(t: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(t) if t else None
    except ValueError:
        return None


def in_hours(now: datetime, hours: list[int], tz_min: int) -> bool:
    h = (now + timedelta(minutes=tz_min)).hour
    a, b = hours
    return a <= h < b if a <= b else (h >= a or h < b)


def _recent(st: dict, now: datetime) -> list[datetime]:
    out = [d for d in (_parse(x) for x in st.get("posted_log") or []) if d and now - d < timedelta(hours=24)]
    return sorted(out)


def _notice(text: str | None) -> None:
    st = store.settings()
    if st.get("notice") != text:
        st["notice"] = text
        store.save_settings(st)


def pick_channel(st: dict) -> str | None:
    chans = [c for c in youtube.channels() if not c.get("needs_login")]
    want = st["autopilot"].get("channel")
    if want:                                       # you chose a channel: never post to a different one
        return want if any(c["id"] == want for c in chans) else None
    return chans[0]["id"] if chans else None


def due_clips(now: datetime, st: dict) -> list[tuple[str, dict]]:
    out = []
    review = st["autopilot"]["review_first"]
    for j in store.listing():
        if j["status"] != "done":
            continue
        job = store.load(j["id"])
        if not rights.can_post(job):                    # the source's permission was never confirmed: nothing from it goes out
            continue
        for c in job.get("clips") or []:
            if c.get("youtube_id") or c.get("status") not in ("ready", "queued") or c.get("attempts", 0) >= 3:
                continue
            if review and not c.get("approved"):
                continue
            when = _parse(c.get("schedule_at"))
            if when and when > now:
                continue
            out.append((job["id"], c))
    return sorted(out, key=lambda x: (x[1].get("schedule_at") or "", x[0], x[1]["n"]))


def post_clip(jid: str, n: int, channel: str, privacy: str, uploader: Callable[..., str] | None = None) -> str:
    """Upload one clip now (a button, or autopilot). Marks 'posting' first and records the result either way."""
    up = uploader or youtube.upload
    job = store.load(jid)
    c = next(x for x in job["clips"] if x["n"] == n)
    if c.get("youtube_id"):
        return c["youtube_id"]

    def mark(j: dict) -> None:
        for x in j["clips"]:
            if x["n"] == n:
                x.update(status="posting", error=None)
    store.update(jid, mark)
    try:
        desc, tags = meta.build(c, job, coach.tags_for_posting())
        vid = up(channel, str(store.jdir(jid) / c["file"]), c["title"], desc, c.get("privacy") or privacy, tags)
    except Exception as e:  # noqa: BLE001
        def fail(j: dict) -> None:
            for x in j["clips"]:
                if x["n"] == n:
                    x.update(status="ready", error=str(e)[:300], attempts=int(x.get("attempts", 0)) + 1)
        store.update(jid, fail)
        raise

    def ok(j: dict) -> None:
        for x in j["clips"]:
            if x["n"] == n:
                x.update(status="posted", youtube_id=vid, posted_at=store.now(), channel=channel, error=None, privacy=c.get("privacy") or privacy)
    store.update(jid, ok)
    try:
        experiments.begin(jid, n)
    except Exception:  # noqa: BLE001 - a test is never worth failing a post for
        pass
    st = store.settings()
    st["posted_log"] = ((st.get("posted_log") or []) + [store.now()])[-300:]
    store.save_settings(st)
    return vid


def tick(uploader: Callable[..., str] | None = None, lister: Callable[[str], list[dict]] | None = None, now: datetime | None = None) -> str:
    """One pass. Returns what it did, in words (the tests and the tab's 'last action' line read it)."""
    now = now or _now()
    st = store.settings()
    ap = st["autopilot"]
    if not ap["enabled"]:
        return "off"
    if ap["paused"]:
        return "paused"
    if not st["rights_ack"]:
        return "waiting: confirm you own the video or have permission to clip it"
    note = _watch(st, lister or youtube.latest_uploads) if ap["auto_make"] else None
    chan = pick_channel(st)
    if not chan:
        _notice("Autopilot has no YouTube login to post with. Connect a channel.")
        return "no channel"
    recent = _recent(st, now)
    if len(recent) >= ap["per_day"]:
        return note or f"daily limit reached ({ap['per_day']})"
    if recent and now - recent[-1] < timedelta(minutes=ap["min_gap_minutes"]):
        return note or "waiting for the minimum gap"
    if not in_hours(now, ap["hours"], st["tz_offset_minutes"]):
        return note or "outside posting hours"
    due = due_clips(now, st)
    if not due:
        return note or "nothing to post"
    jid, c = due[0]
    try:
        vid = post_clip(jid, c["n"], chan, ap["privacy"], uploader)
    except youtube.NeedsLogin as e:
        st = store.settings()
        st["autopilot"]["paused"] = True
        st["notice"] = str(e)
        store.save_settings(st)
        return "paused: login expired"
    except Exception as e:  # noqa: BLE001
        _notice("The last post failed: " + str(e)[:200])
        return "post failed"
    _notice(None)
    return f"posted {vid}"


def _watch(st: dict, lister: Callable[[str], list[dict]]) -> str | None:
    """New uploads on the watched channels become jobs by themselves. The first look only records what is already there (no backlog)."""
    changed = False
    started = None
    for w in st["watch"]:
        try:
            items = lister(w["channel_id"])
        except Exception:  # noqa: BLE001
            continue
        seen = set(w.get("seen") or [])
        fresh = [i for i in items if i["id"] not in seen]
        if not seen and items:                       # first look: remember, don't make
            w["seen"] = [i["id"] for i in items]
            changed = True
            continue
        if fresh and not started:
            v = fresh[-1]
            o = pipeline.build_opts({"count": st["autopilot"]["make_per_video"]})
            job = pipeline.new_job(o, {"kind": "url", "url": f"https://www.youtube.com/watch?v={v['id']}", "name": v["title"]}, auto=True)
            pipeline.start(job["id"])
            w["seen"] = (w.get("seen") or []) + [v["id"]]
            changed = True
            started = f"started clips from '{v['title'][:40]}'"
    if changed:
        cur = store.settings()
        cur["watch"] = st["watch"]
        store.save_settings(cur)
    return started


def refresh_stats(force: bool = False) -> int:
    """Views and likes for what was posted (one quota unit per 50 videos)."""
    global _last_stats
    if not force and time.time() - _last_stats < 1800:
        return 0
    _last_stats = time.time()
    by_chan: dict[str, list[tuple[str, int, str]]] = {}
    for j in store.listing():
        for c in store.load(j["id"]).get("clips") or []:
            if c.get("youtube_id") and c.get("channel"):
                by_chan.setdefault(c["channel"], []).append((j["id"], c["n"], c["youtube_id"]))
    n = 0
    for chan, rows in by_chan.items():
        try:
            data = youtube.stats(chan, [r[2] for r in rows])
        except Exception:  # noqa: BLE001
            continue
        for jid, num, vid in rows:
            if vid in data:
                def f(job: dict, num: int = num, vid: str = vid) -> None:
                    for x in job["clips"]:
                        if x["n"] == num:
                            x["stats"] = data[vid] | {"at": store.now()}
                store.update(jid, f)
                n += 1
    return n


def _run() -> None:
    while not _stop.wait(TICK):
        try:
            for step in (tick, refresh_stats, postqueue.tick, postqueue.refresh, coach.maybe_analyse, retention.refresh, experiments.tick, comments.maybe_sync):
                try:
                    step()
                except Exception:  # noqa: BLE001 - one broken step must not stop the others, and the loop must never die
                    pass
        except Exception:  # noqa: BLE001
            pass


def start_loop() -> None:
    global _loop
    if _loop and _loop.is_alive():
        return
    _stop.clear()
    _loop = threading.Thread(target=_run, daemon=True, name="autoclip-autopilot")
    _loop.start()
    try:
        from . import live
        live.resume()                                          # live-stream watching picks up again after a restart if it was on
    except Exception:  # noqa: BLE001 - never stop the app from starting
        pass


def stop_loop() -> None:
    _stop.set()


def status() -> dict:
    st = store.settings()
    now = _now()
    return {"recent": len(_recent(st, now)), "per_day": st["autopilot"]["per_day"], "in_hours": in_hours(now, st["autopilot"]["hours"], st["tz_offset_minutes"]),
            "notice": st.get("notice"), "waiting": len(due_clips(now, st)) if st["rights_ack"] else 0, "running": bool(_loop and _loop.is_alive())}
