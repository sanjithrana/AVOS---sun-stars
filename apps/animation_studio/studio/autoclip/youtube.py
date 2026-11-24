"""YouTube through Google's own APIs, signed in as YOU with a Google Cloud client that YOU create (free). No cookies, no scraping, no
third-party program ever sees your login: Google sends a one-time code to this studio, the studio swaps it for tokens and keeps them in
accounts.json (owner-only, never sent to the page).

Setup, once (the Auto Clip tab walks through it):
  1. console.cloud.google.com: new project, enable "YouTube Data API v3" (and "YouTube Analytics API" for views and earnings).
  2. OAuth consent screen: External. Add yourself as a test user. Set the app to "In production" when you can: Google expires the logins of
     apps left in "Testing", which would stop autopilot posting after a few days.
  3. Credentials: OAuth client ID, type "Web application", authorised redirect URI = the one shown in the tab.
  4. Paste the client ID and secret in the tab, press Connect.
"""
from __future__ import annotations

import re
import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from . import store

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly", "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
          "https://www.googleapis.com/auth/youtube.force-ssl"]


class NeedsLogin(RuntimeError):
    """Google no longer accepts the saved login (revoked, expired, or the app is still in Testing): connect again."""


def _req(method: str, url: str, **kw: Any) -> httpx.Response:
    kw.setdefault("timeout", 60)
    return httpx.request(method, url, **kw)


def _err(r: httpx.Response) -> str:
    try:
        e = r.json().get("error")
        return (e.get("message") if isinstance(e, dict) else str(e) or r.text)[:240]
    except Exception:  # noqa: BLE001
        return r.text[:240] or f"HTTP {r.status_code}"


# ---------- the Google Cloud client ----------
def set_client(client_id: str, client_secret: str) -> None:
    a = store.accounts()
    a["client"] = {"id": client_id.strip(), "secret": client_secret.strip()}
    store.save_accounts(a)


def has_client() -> bool:
    c = store.accounts().get("client") or {}
    return bool(c.get("id") and c.get("secret"))


def redirect_uri(origin: str) -> str:
    return origin.rstrip("/") + "/studio-api/autoclip/youtube/callback"


def auth_url(origin: str) -> str:
    a = store.accounts()
    c = a.get("client") or {}
    if not (c.get("id") and c.get("secret")):
        raise RuntimeError("Paste your Google client ID and secret first.")
    state = secrets.token_urlsafe(24)
    a.setdefault("pending", {})
    a["pending"] = {k: v for k, v in a["pending"].items() if time.time() - v["t"] < 900}      # forget old attempts
    a["pending"][state] = {"redirect": redirect_uri(origin), "t": time.time(), "origin": origin.rstrip("/")}
    store.save_accounts(a)
    q = {"client_id": c["id"], "redirect_uri": a["pending"][state]["redirect"], "response_type": "code", "scope": " ".join(SCOPES),
         "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
    return AUTH + "?" + urllib.parse.urlencode(q)


def finish(code: str, state: str) -> dict:
    a = store.accounts()
    pend = (a.get("pending") or {}).pop(state, None)
    if not pend or time.time() - pend["t"] > 900:
        raise RuntimeError("That sign-in link has expired or is not from this studio. Press Connect again.")
    c = a["client"]
    r = _req("POST", TOKEN, data={"code": code, "client_id": c["id"], "client_secret": c["secret"], "redirect_uri": pend["redirect"], "grant_type": "authorization_code"})
    if r.status_code != 200:
        raise RuntimeError("Google refused the sign-in: " + _err(r))
    tok = r.json()
    if not tok.get("refresh_token"):
        raise RuntimeError("Google gave no refresh token. Remove this app at myaccount.google.com/permissions and connect again.")
    info = _req("GET", f"{API}/channels", params={"part": "snippet,statistics", "mine": "true"}, headers={"Authorization": "Bearer " + tok["access_token"]})
    items = (info.json().get("items") if info.status_code == 200 else None) or []
    if not items:
        raise RuntimeError("That Google account has no YouTube channel. Create one at youtube.com first, then connect again.")
    ch = items[0]
    a.setdefault("channels", {})[ch["id"]] = {
        "id": ch["id"], "title": ch["snippet"]["title"], "thumb": (ch["snippet"].get("thumbnails", {}).get("default") or {}).get("url", ""),
        "subs": int((ch.get("statistics") or {}).get("subscriberCount") or 0), "refresh": tok["refresh_token"], "access": tok["access_token"],
        "expires": time.time() + int(tok.get("expires_in", 3600)) - 60, "scopes": tok.get("scope", ""), "connected": store.now(), "needs_login": False}
    store.save_accounts(a)
    return {"id": ch["id"], "title": ch["snippet"]["title"], "origin": pend.get("origin", "")}


def channels() -> list[dict]:
    """What the page may see about each connected channel: never a token."""
    return [{k: c.get(k) for k in ("id", "title", "thumb", "subs", "connected", "needs_login")} | {
        "revenue_scope": "yt-analytics-monetary" in (c.get("scopes") or "")} for c in (store.accounts().get("channels") or {}).values()]


def disconnect(cid: str) -> bool:
    a = store.accounts()
    ch = (a.get("channels") or {}).pop(cid, None)
    if ch:
        try:
            _req("POST", "https://oauth2.googleapis.com/revoke", data={"token": ch.get("refresh")}, timeout=20)     # take the permission back at Google too
        except Exception:  # noqa: BLE001 - removed here either way
            pass
        store.save_accounts(a)
    return bool(ch)


def token(cid: str) -> str:
    a = store.accounts()
    ch = (a.get("channels") or {}).get(cid)
    if not ch:
        raise RuntimeError("That channel is not connected.")
    if ch.get("access") and ch.get("expires", 0) > time.time():
        return ch["access"]
    c = a.get("client") or {}
    r = _req("POST", TOKEN, data={"client_id": c.get("id"), "client_secret": c.get("secret"), "refresh_token": ch["refresh"], "grant_type": "refresh_token"})
    if r.status_code != 200:
        if "invalid_grant" in r.text or r.status_code in (400, 401):
            ch["needs_login"] = True
            store.save_accounts(a)
            raise NeedsLogin("Google no longer accepts the saved login for " + ch.get("title", cid) + ". Connect it again in Auto Clip.")
        raise RuntimeError("Could not refresh the login: " + _err(r))
    ch["access"], ch["expires"], ch["needs_login"] = r.json()["access_token"], time.time() + int(r.json().get("expires_in", 3600)) - 60, False
    store.save_accounts(a)
    return ch["access"]


# ---------- uploading ----------
def clean_text(s: str, n: int) -> str:
    return re.sub(r"[<>]", "", " ".join(str(s or "").split()))[:n]


LAST_PRIVACY: dict[str, str] = {}      # video id -> the visibility YouTube really gave it


def upload(cid: str, path: str, title: str, description: str = "", privacy: str = "private", tags: list[str] | None = None, publish_at: str | None = None) -> str:
    """A resumable upload of one finished short. Returns the new video's id. With publish_at (ISO time) it is uploaded private and YouTube itself
    makes it public at that time, even if this studio is off by then."""
    if privacy not in ("private", "unlisted", "public"):
        privacy = "private"
    f = Path(path)
    if not f.is_file():
        raise RuntimeError("The clip's file is missing.")
    desc = clean_text(description, 4800)
    if "#shorts" not in desc.lower():
        desc = (desc + "\n\n#Shorts").strip()
    meta = {"snippet": {"title": clean_text(title, 95) or "Highlight", "description": desc, "tags": [clean_text(t, 30) for t in (tags or [])][:10], "categoryId": "22"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    if publish_at:
        meta["status"].update(privacyStatus="private", publishAt=publish_at.replace("+00:00", "Z"))
    hdr = {"Authorization": "Bearer " + token(cid), "Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": "video/mp4",
           "X-Upload-Content-Length": str(f.stat().st_size)}
    r = _req("POST", UPLOAD, params={"uploadType": "resumable", "part": "snippet,status"}, json=meta, headers=hdr)
    if r.status_code != 200 or not r.headers.get("location"):
        raise RuntimeError("YouTube would not start the upload: " + _err(r))
    with f.open("rb") as fh:
        up = _req("PUT", r.headers["location"], content=fh, headers={"Content-Type": "video/mp4", "Content-Length": str(f.stat().st_size)}, timeout=1800)
    if up.status_code not in (200, 201):
        raise RuntimeError("YouTube refused the upload: " + _err(up))
    j = up.json()
    LAST_PRIVACY[j["id"]] = str((j.get("status") or {}).get("privacyStatus") or "")
    return j["id"]


def set_thumbnail(cid: str, video_id: str, image: str) -> None:
    """Put a cover on a posted video. YouTube may refuse it for Shorts or for channels not yet verified: the caller treats that as a note, not a failure."""
    f = Path(image)
    if not f.is_file():
        raise RuntimeError("no cover image")
    r = _req("POST", "https://www.googleapis.com/upload/youtube/v3/thumbnails/set", params={"videoId": video_id, "uploadType": "media"},
             content=f.read_bytes(), headers={"Authorization": "Bearer " + token(cid), "Content-Type": "image/jpeg"}, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(_err(r))


# ---------- numbers ----------
def stats(cid: str, ids: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        r = _req("GET", f"{API}/videos", params={"part": "statistics,status", "id": ",".join(ids[i: i + 50])}, headers={"Authorization": "Bearer " + token(cid)})
        if r.status_code != 200:
            raise RuntimeError("Could not read the numbers: " + _err(r))
        for v in r.json().get("items") or []:
            s = v.get("statistics") or {}
            out[v["id"]] = {"views": int(s.get("viewCount") or 0), "likes": int(s.get("likeCount") or 0), "comments": int(s.get("commentCount") or 0),
                            "privacy": (v.get("status") or {}).get("privacyStatus")}
    return out


def revenue(cid: str, start: str, end: str) -> dict | None:
    """Estimated earnings for the channel, or None: only channels in the YouTube Partner Programme have any, and it needs the earnings permission."""
    try:
        r = _req("GET", ANALYTICS, params={"ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": "views,estimatedRevenue"},
                 headers={"Authorization": "Bearer " + token(cid)})
        if r.status_code != 200:
            return None
        row = (r.json().get("rows") or [[0, 0]])[0]
        return {"views": int(row[0]), "estimated_revenue": float(row[1])}
    except NeedsLogin:
        raise
    except Exception:  # noqa: BLE001
        return None


def latest_uploads(channel_id: str) -> list[dict]:
    """A channel's newest uploads from its public RSS feed (no key, no quota)."""
    r = _req("GET", "https://www.youtube.com/feeds/videos.xml", params={"channel_id": channel_id}, timeout=30)
    if r.status_code != 200:
        return []
    out = []
    for m in re.finditer(r"<entry>.*?<yt:videoId>([\w-]{11})</yt:videoId>.*?<title>(.*?)</title>", r.text, re.S):
        out.append({"id": m.group(1), "title": re.sub(r"&(amp|lt|gt|quot|#39);", lambda x: {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "#39": "'"}[x.group(1)], m.group(2))[:120]})
    return out[:15]


# ---------- retention (YouTube Analytics API) ----------
class NeedsScope(RuntimeError):
    """The saved login was granted before this feature existed: connect the channel again to allow it."""


def retention(cid: str, video_id: str, since: str, until: str) -> dict | None:
    """How long people watched one video: {"avg_view_pct", "avg_view_sec", "minutes", "views", "curve": [20 numbers 0..1+]} where curve[i] is the share of viewers still watching
    at i/20 of the way through. None when Google has no numbers yet (they lag 2-3 days, and a video needs some views)."""
    h = {"Authorization": "Bearer " + token(cid)}
    base = {"ids": "channel==MINE", "startDate": since, "endDate": until, "filters": f"video=={video_id}"}
    r = _req("GET", ANALYTICS, params=base | {"metrics": "views,averageViewDuration,averageViewPercentage,estimatedMinutesWatched"}, headers=h)
    if r.status_code in (401, 403):
        raise NeedsScope(_err(r))
    if r.status_code != 200:
        return None
    row = (r.json().get("rows") or [None])[0]
    if not row or not int(row[0] or 0):
        return None
    out: dict[str, Any] = {"views": int(row[0]), "avg_view_sec": round(float(row[1] or 0), 1), "avg_view_pct": round(float(row[2] or 0), 1), "minutes": round(float(row[3] or 0), 1), "curve": []}
    c = _req("GET", ANALYTICS, params=base | {"dimensions": "elapsedVideoTimeRatio", "metrics": "audienceWatchRatio"}, headers=h)
    if c.status_code == 200:
        pts = sorted((float(x[0]), float(x[1])) for x in (c.json().get("rows") or []))
        if len(pts) >= 10:
            out["curve"] = [round(sum(v for t, v in pts if i / 20 <= t < (i + 1) / 20) / max(1, sum(1 for t, _ in pts if i / 20 <= t < (i + 1) / 20)), 3) for i in range(20)]
    return out


def set_title(cid: str, video_id: str, title: str) -> None:
    """Change a posted video's title (everything else about it is kept: YouTube's update call needs the whole snippet back)."""
    h = {"Authorization": "Bearer " + token(cid)}
    r = _req("GET", f"{API}/videos", params={"part": "snippet", "id": video_id}, headers=h)
    items = r.json().get("items") if r.status_code == 200 else None
    if not items:
        raise RuntimeError("Could not read the video: " + _err(r))
    sn = items[0]["snippet"]
    body = {"id": video_id, "snippet": {"title": clean_text(title, 100), "description": sn.get("description", ""), "categoryId": sn.get("categoryId", "22"),
                                        **({"tags": sn["tags"]} if sn.get("tags") else {})}}
    u = _req("PUT", f"{API}/videos", params={"part": "snippet"}, json=body, headers=h)
    if u.status_code != 200:
        raise RuntimeError("YouTube refused the new title: " + _err(u))


# ---------- comments ----------
def comments(cid: str, video_id: str, limit: int = 50) -> list[dict]:
    """Top-level comments on one of your videos, newest first."""
    r = _req("GET", f"{API}/commentThreads", params={"part": "snippet", "videoId": video_id, "maxResults": min(100, limit), "order": "time", "textFormat": "plainText"},
             headers={"Authorization": "Bearer " + token(cid)})
    if r.status_code == 403 and "commentsDisabled" in r.text:
        return []
    if r.status_code in (401, 403):
        raise NeedsScope(_err(r))
    if r.status_code != 200:
        raise RuntimeError("Could not read comments: " + _err(r))
    out = []
    for it in r.json().get("items") or []:
        sn = (it.get("snippet") or {})
        top = sn.get("topLevelComment") or {}
        t = top.get("snippet") or {}
        out.append({"id": top.get("id") or it.get("id"), "author": t.get("authorDisplayName") or "", "author_channel": ((t.get("authorChannelId") or {}).get("value") or ""),
                    "text": t.get("textDisplay") or t.get("textOriginal") or "", "likes": int(t.get("likeCount") or 0), "at": t.get("publishedAt") or "", "replies": int(sn.get("totalReplyCount") or 0)})
    return out


def reply(cid: str, parent_id: str, text: str) -> str:
    r = _req("POST", f"{API}/comments", params={"part": "snippet"}, json={"snippet": {"parentId": parent_id, "textOriginal": clean_text(text, 9000)}},
             headers={"Authorization": "Bearer " + token(cid)})
    if r.status_code in (401, 403):
        raise NeedsScope(_err(r))
    if r.status_code != 200:
        raise RuntimeError("YouTube refused the reply: " + _err(r))
    return r.json().get("id", "")


def hold_comment(cid: str, comment_id: str) -> None:
    """Hold a comment for review on YouTube (it disappears from the video until you approve it in YouTube Studio)."""
    r = _req("POST", f"{API}/comments/setModerationStatus", params={"id": comment_id, "moderationStatus": "heldForReview"}, headers={"Authorization": "Bearer " + token(cid)})
    if r.status_code in (401, 403):
        raise NeedsScope(_err(r))
    if r.status_code not in (200, 204):
        raise RuntimeError("YouTube refused to hold it: " + _err(r))
