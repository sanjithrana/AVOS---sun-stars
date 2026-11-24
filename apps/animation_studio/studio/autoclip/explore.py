"""Explore: what is trending right now, by category and country, ready to clip.

Categories YouTube has a trending chart for (Gaming, Comedy, Sports, News, Education, Tech, Entertainment) come from that chart:
one cheap API call (1 quota unit) through your connected channel. The others (Podcasts, Interviews, Business, True crime, Fitness)
are a search for the most-viewed long videos of the last week (100 units), kept for 4 hours. Without a connected channel, a plain
yt-dlp search fills in. Only long videos (8 minutes and more) or live streams are listed: short ones have nothing to clip."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from . import store

CATS: dict[str, dict[str, Any]] = {
    "all": {"label": "All", "chart": "", "q": "trending"},
    "podcasts": {"label": "Podcasts", "q": "podcast full episode"},
    "interviews": {"label": "Interviews", "q": "interview full"},
    "business": {"label": "Business", "q": "business podcast startup founder"},
    "comedy": {"label": "Comedy", "chart": "23", "q": "stand up comedy full show"},
    "true_crime": {"label": "True crime", "q": "true crime documentary"},
    "news": {"label": "News", "chart": "25", "q": "news debate full"},
    "education": {"label": "Education", "chart": "27", "q": "explained lecture"},
    "sports": {"label": "Sports", "chart": "17", "q": "match highlights full podcast reaction"},
    "gaming": {"label": "Gaming", "chart": "20", "q": "gameplay live stream"},
    "fitness": {"label": "Fitness", "q": "fitness podcast workout"},
    "tech": {"label": "Tech", "chart": "28", "q": "tech review podcast"},
    "entertainment": {"label": "Entertainment", "chart": "24", "q": "full episode show"},
    "music": {"label": "Music", "chart": "10", "q": "live concert performance"},
    "film": {"label": "Movies", "chart": "1", "q": "movie review trailer reaction"},
    "people": {"label": "Vlogs", "chart": "22", "q": "vlog"},
    "howto": {"label": "How-to", "chart": "26", "q": "how to tutorial"},
    "autos": {"label": "Cars", "chart": "2", "q": "car review"},
    "travel": {"label": "Travel", "chart": "19", "q": "travel vlog"},
    "pets": {"label": "Pets & animals", "chart": "15", "q": "animals"},
}
# Channels whose long videos and streams get clipped a lot, per category (their newest uploads are read: 1 quota unit each).
# A handle that does not resolve is simply skipped. Add your own on the Explore tab.
WATCH: dict[str, list[str]] = {
    "podcasts": ["@joerogan", "@lexfridman", "@TheDiaryOfACEO", "@rajshamani", "@BeerBiceps", "@flagrant", "@ImPaulRosolie", "@theo_von"],
    "interviews": ["@FirstWeFeast", "@TheDiaryOfACEO", "@rajshamani", "@BeerBiceps", "@ColinandSamir"],
    "business": ["@rajshamani", "@TheDiaryOfACEO", "@AlexHormozi", "@MyFirstMillionPod", "@ankurwarikoo"],
    "comedy": ["@SamayRainaOfficial", "@ZakirKhan", "@NetflixIsAJoke", "@KillTonyPodcast", "@AbhishekUpmanyu", "@AnubhavSinghBassi"],
    "true_crime": ["@MrBallen", "@BaileySarian", "@JCSCriminalPsychology", "@EWUFIRES"],
    "news": ["@dhruvrathee", "@PiersMorganUncensored", "@TheYoungTurks", "@timcast"],
    "education": ["@veritasium", "@kurzgesagt", "@dhruvrathee", "@hubermanlab"],
    "sports": ["@SkySportsPremierLeague", "@SkySportsFootball", "@TheOverlap", "@ESPNcricinfo", "@NBA"],
    "gaming": ["@IShowSpeed", "@KaiCenat", "@xQcOW", "@CarryMinati", "@CaseOh_", "@Pokimane", "@jynxzi"],
    "fitness": ["@hubermanlab", "@JeffNippard", "@MikeThurston", "@WillTennyson"],
    "tech": ["@mkbhd", "@LinusTechTips", "@TechnicalGuruji", "@marquesbrownlee"],
}
REGIONS = {"IN": "India", "US": "United States", "GB": "United Kingdom", "CA": "Canada", "AU": "Australia"}
MIN_SECONDS = 8 * 60


def _dur(iso: str) -> int:
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def _row(v: dict) -> dict:
    sn, st, cd = v.get("snippet") or {}, v.get("statistics") or {}, v.get("contentDetails") or {}
    th = (sn.get("thumbnails") or {})
    pic = (th.get("maxres") or th.get("high") or th.get("medium") or th.get("default") or {}).get("url") or f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"
    return {"id": v["id"], "url": f"https://www.youtube.com/watch?v={v['id']}", "title": sn.get("title") or "", "channel": sn.get("channelTitle") or "",
            "thumb": pic, "views": int(st.get("viewCount") or 0), "seconds": _dur(cd.get("duration") or ""), "published": sn.get("publishedAt") or "",
            "live": sn.get("liveBroadcastContent") == "live"}


def _api(cat: dict, region: str) -> list[dict] | None:
    from . import youtube
    h = _auth()
    if h is None:
        return None
    if "chart" in cat:                                             # YouTube's trending chart: "" = every category; 50 a page, 1 unit a page
        rows: list[dict] = []
        tok = None
        for _ in range(4 if not cat["chart"] else 2):
            params = {"part": "snippet,statistics,contentDetails", "chart": "mostPopular", "regionCode": region, "maxResults": 50}
            if cat["chart"]:
                params["videoCategoryId"] = cat["chart"]
            if tok:
                params["pageToken"] = tok
            r = youtube._req("GET", f"{youtube.API}/videos", params=params, headers=h)
            if r.status_code != 200:
                if rows or r.status_code in (400, 404):                # a category with no chart in this country falls through to search
                    break
                raise RuntimeError("YouTube refused the trending list: " + youtube._err(r))
            rows += [_row(v) for v in r.json().get("items") or []]
            tok = r.json().get("nextPageToken")
            if not tok:
                break
        if rows:
            return rows
    after = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = youtube._req("GET", f"{youtube.API}/search", params={"part": "snippet", "q": cat["q"], "type": "video", "order": "viewCount", "publishedAfter": after,
                                                              "regionCode": region, "videoDuration": "long", "maxResults": 30}, headers=h)
    if r.status_code != 200:
        raise RuntimeError("YouTube search refused: " + youtube._err(r))
    ids = [(it.get("id") or {}).get("videoId") for it in r.json().get("items") or []]
    ids = [i for i in ids if i]
    if not ids:
        return []
    r = youtube._req("GET", f"{youtube.API}/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids)}, headers=h)
    if r.status_code != 200:
        raise RuntimeError("YouTube refused the video details: " + youtube._err(r))
    return [_row(v) for v in r.json().get("items") or []]


def handles_for(cat_id: str) -> list[str]:
    from . import store as _s
    mine = list(_s.settings().get("explore_channels") or [])
    if cat_id == "all":
        seen: list[str] = []
        for k in ("podcasts", "comedy", "gaming", "sports", "interviews", "business", "news", "true_crime", "education", "tech", "fitness"):  # noqa: E501
            for h in WATCH[k][:2]:
                if h not in seen:
                    seen.append(h)
        return mine + seen
    return mine + [h for h in WATCH.get(cat_id, []) if h not in mine]


_LOCK = __import__("threading").Lock()


def _uploads(h: dict, handle: str) -> str | None:
    """A channel's uploads playlist id from its @handle (looked up once, then remembered)."""
    from . import youtube
    memo = store.ROOT / "explore" / "uploads.json"
    with _LOCK:
        known = store._read(memo, {})
    if handle in known:
        return known[handle] or None
    pid = None
    try:
        r = youtube._req("GET", f"{youtube.API}/channels", params={"part": "contentDetails", "forHandle": handle}, headers=h, timeout=15)
        if r.status_code == 200:
            it = (r.json().get("items") or [None])[0]
            pid = ((it or {}).get("contentDetails") or {}).get("relatedPlaylists", {}).get("uploads")
        elif r.status_code >= 500:
            return None                                          # YouTube hiccup: try again next time, do not remember
    except Exception:  # noqa: BLE001
        return None
    with _LOCK:
        known = store._read(memo, {})
        known[handle] = pid or ""
        memo.parent.mkdir(parents=True, exist_ok=True)
        store._write(memo, known)
    return pid


def _one_channel(h: dict, hd: str, per: int, since: datetime) -> list[str]:
    from . import youtube
    pid = _uploads(h, hd)
    if not pid:
        return []
    try:
        r = youtube._req("GET", f"{youtube.API}/playlistItems", params={"part": "contentDetails", "playlistId": pid, "maxResults": per}, headers=h, timeout=15)
    except Exception:  # noqa: BLE001
        return []
    if r.status_code != 200:
        return []
    out = []
    for it in r.json().get("items") or []:
        cd = it.get("contentDetails") or {}
        at = cd.get("videoPublishedAt") or ""
        try:
            if at and datetime.fromisoformat(at.replace("Z", "+00:00")) < since:
                continue
        except ValueError:
            pass
        if cd.get("videoId"):
            out.append(cd["videoId"])
    return out


def _watch_api(h: dict, handles: list[str], per: int = 6) -> list[str]:
    """The newest video ids of each watched channel (last 3 weeks), all channels read at the same time (a few seconds, not a minute)."""
    from concurrent.futures import ThreadPoolExecutor
    since = datetime.now(timezone.utc) - timedelta(days=21)
    with ThreadPoolExecutor(max_workers=12) as ex:
        res = list(ex.map(lambda hd: _one_channel(h, hd, per, since), handles))
    return [i for r in res for i in r]


def _details(h: dict, ids: list[str]) -> list[dict]:
    from . import youtube
    from concurrent.futures import ThreadPoolExecutor
    ids = list(dict.fromkeys(ids))

    def page(i: int) -> list[dict]:
        try:
            r = youtube._req("GET", f"{youtube.API}/videos", params={"part": "snippet,statistics,contentDetails", "id": ",".join(ids[i: i + 50])}, headers=h, timeout=20)
        except Exception:  # noqa: BLE001
            return []
        return [_row(v) for v in r.json().get("items") or []] if r.status_code == 200 else []
    with ThreadPoolExecutor(max_workers=4) as ex:
        return [x for rows in ex.map(page, range(0, len(ids), 50)) for x in rows]


def _watch_search(handles: list[str], per: int = 4) -> list[dict]:
    """No login: each watched channel's newest videos and streams, read with yt-dlp."""
    from .research import _ytdlp
    out: list[dict] = []
    for hd in handles[:14]:
        for tab in ("videos", "streams"):
            raw = _ytdlp(["--flat-playlist", "--dump-single-json", "--playlist-items", f"1-{per}", f"https://www.youtube.com/{hd}/{tab}"], 60)
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            for e in d.get("entries") or []:
                if e and e.get("id"):
                    out.append({"id": e["id"], "url": f"https://www.youtube.com/watch?v={e['id']}", "title": e.get("title") or "", "channel": d.get("channel") or d.get("uploader") or hd,
                                "thumb": f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg", "views": int(e.get("view_count") or 0), "seconds": int(e.get("duration") or 0),
                                "published": datetime.fromtimestamp(e["timestamp"], timezone.utc).isoformat() if e.get("timestamp") else "", "live": e.get("live_status") == "is_live"})
    return out


def per_hour(x: dict) -> int:
    """Views per hour since it went up: how fast it is moving right now."""
    try:
        hrs = max(1.0, (datetime.now(timezone.utc) - datetime.fromisoformat(x["published"].replace("Z", "+00:00"))).total_seconds() / 3600)
    except (ValueError, KeyError, AttributeError):
        return 0
    return int(x.get("views", 0) / hrs)


def _search(cat: dict) -> list[dict]:
    """No login: yt-dlp's search, newest uploads first."""
    from .research import _ytdlp
    raw = _ytdlp(["--flat-playlist", "--dump-single-json", f"ytsearchdate30:{cat['q']}"], 120)
    try:
        ents = json.loads(raw).get("entries") or []
    except ValueError:
        return []
    out = []
    for e in ents:
        if not e or not e.get("id"):
            continue
        out.append({"id": e["id"], "url": f"https://www.youtube.com/watch?v={e['id']}", "title": e.get("title") or "", "channel": e.get("channel") or e.get("uploader") or "",
                    "thumb": f"https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg", "views": int(e.get("view_count") or 0), "seconds": int(e.get("duration") or 0),
                    "published": "", "live": e.get("live_status") == "is_live"})
    return out


def trending(cat_id: str = "all", region: str = "IN", fresh: bool = False, length: str = "long") -> dict:
    res = _trending(cat_id, region, fresh)
    keep = [x for x in res["items"] if length == "any" or x["live"] or x["seconds"] >= MIN_SECONDS]
    return {**res, "items": keep[:120], "length": length, "total": len(res["items"])}


def _trending(cat_id: str, region: str, fresh: bool) -> dict:
    """{"cat", "region", "updated", "source", "items": [...]} — the newest long videos and streams of the watched channels, plus the
    country's trending chart, ranked by views per hour. Cached for an hour."""
    cat_id = cat_id if cat_id in CATS else "all"
    region = region if region in REGIONS else "IN"
    cat = CATS[cat_id]
    p = store.ROOT / "explore" / f"v2-{cat_id}-{region}.json"
    hit = store._read(p, None)
    if hit and not fresh and time.time() - float(hit.get("t", 0)) < 3600:
        return hit
    handles = handles_for(cat_id)
    items: list[dict] = []
    source, err = "youtube", None
    try:
        h = _auth()
        if h is None:
            raise LookupError("no channel")
        ids = _watch_api(h, handles)
        items = _details(h, ids)
        chart = _api(cat, region) if "chart" in cat else None
        items += chart or []
        if len([x for x in items if x["live"] or x["seconds"] >= MIN_SECONDS]) < 9:      # thin: add a search (100 units, so only when needed)
            items += _api({"q": cat["q"]}, region) or []
    except LookupError:
        source = "search"
    except Exception as e:  # noqa: BLE001
        source, err = "search", str(e)[:200]
    if source == "search":
        items = _watch_search(handles) + _search(cat)
    seen: set[str] = set()
    uniq = []
    for x in items:
        if x["id"] not in seen:
            seen.add(x["id"])
            x["per_hour"] = per_hour(x)
            uniq.append(x)
    uniq.sort(key=lambda x: (not x["live"], -(x["per_hour"] or x["views"] / 500)))
    res = {"cat": cat_id, "region": region, "t": time.time(), "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "source": source, "items": uniq[:250],
           "watching": handles}
    if err:
        res["note"] = "The YouTube API refused, so this is a plain search: " + err
    if uniq or not hit:
        p.parent.mkdir(parents=True, exist_ok=True)
        store._write(p, res)
        return res
    return hit


def _auth() -> dict | None:
    from . import youtube
    chans = [c for c in youtube.channels() if not c.get("needs_login")]
    return {"Authorization": "Bearer " + youtube.token(chans[0]["id"])} if chans else None


def add_channel(handle: str) -> list[str]:
    h = "@" + re.sub(r"[^A-Za-z0-9._-]", "", str(handle).strip().split("/")[-1].lstrip("@"))[:40]
    if len(h) < 3:
        raise ValueError("Type the channel's @handle, for example @IShowSpeed.")
    cur = store.settings()
    lst = [x for x in (cur.get("explore_channels") or []) if x.lower() != h.lower()]
    cur["explore_channels"] = ([h] + lst)[:30]
    store.save_settings(cur)
    for f in (store.ROOT / "explore").glob("*-*.json"):
        f.unlink(missing_ok=True)
    return cur["explore_channels"]


def remove_channel(handle: str) -> list[str]:
    cur = store.settings()
    cur["explore_channels"] = [x for x in (cur.get("explore_channels") or []) if x.lower() != str(handle).lower()]
    store.save_settings(cur)
    for f in (store.ROOT / "explore").glob("*-*.json"):
        f.unlink(missing_ok=True)
    return cur["explore_channels"]
