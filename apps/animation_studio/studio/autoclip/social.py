"""Other places to post: Instagram Reels, Facebook Pages and TikTok, signed in as YOU through developer apps that YOU create (free).
Same rules as youtube.py: no cookies, no scraping; tokens live in accounts.json["social"] (owner-only) and never reach the page.

One account id looks like "instagram:<id>", "facebook:<id>" or "tiktok:<id>", so the post queue can hold them next to YouTube channel ids.
  * Meta (one app, one login) gives every Facebook Page you manage and the Instagram professional account linked to each.
    Instagram Reels are sent with Meta's resumable upload, so no public web address is needed and localhost works.
  * TikTok uses the Content Posting API. Until TikTok audits your app it only accepts private ("only me") posts.
X, LinkedIn and Pinterest are listed as planned in PLATFORMS and not built yet.
"""
from __future__ import annotations

import secrets
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx

from . import store, youtube

GRAPH = "v21.0"
FB_AUTH = f"https://www.facebook.com/{GRAPH}/dialog/oauth"
FB_API = f"https://graph.facebook.com/{GRAPH}"
FB_VIDEO = f"https://graph-video.facebook.com/{GRAPH}"
IG_UPLOAD = f"https://rupload.facebook.com/ig-api-upload/{GRAPH}"
META_SCOPES = ["pages_show_list", "pages_read_engagement", "pages_manage_posts", "instagram_basic", "instagram_content_publish", "business_management"]
TT_AUTH = "https://www.tiktok.com/v2/auth/authorize/"
TT_API = "https://open.tiktokapis.com/v2"
TT_SCOPES = ["user.info.basic", "video.publish"]

# What the Connections page draws. "key" is the app id, "secret" the app secret, both stored on this studio only.
PLATFORMS: list[dict] = [
    {"id": "meta", "name": "Instagram and Facebook", "status": "ready", "makes": ["instagram", "facebook"], "id_label": "App ID", "secret_label": "App secret",
     "steps": [
         "Your Instagram must be a Professional account (Business or Creator) linked to a Facebook Page. Switch it in Instagram → Settings → Account type.",
         "Go to developers.facebook.com → My Apps → Create App. Choose \"Other\", then type \"Business\".",
         "Add the products \"Facebook Login for Business\" (or \"Facebook Login\") and \"Instagram\" if it asks.",
         "In Facebook Login → Settings, add the redirect address shown below under \"Valid OAuth Redirect URIs\".",
         "In App settings → Basic, copy the App ID and App secret and paste them here. Keep the app in Development mode and add yourself as an admin or tester: that is allowed for your own accounts without Meta review.",
     ],
     "notes": ["Instagram posts are always public. The privacy choice only applies to Facebook (private = saved unpublished).",
               "Reels must be 3 to 90 seconds, vertical, MP4. Instagram allows about 25 API posts per day per account."]},
    {"id": "tiktok", "name": "TikTok", "status": "ready", "makes": ["tiktok"], "id_label": "Client key", "secret_label": "Client secret",
     "steps": [
         "Go to developers.tiktok.com → Manage apps → Connect an app.",
         "Add the products \"Login Kit\" and \"Content Posting API\" (turn on Direct Post). Scopes: user.info.basic and video.publish.",
         "TikTok needs a web address that starts with https for the redirect. localhost is usually refused, so use a free tunnel (e.g. a Cloudflare tunnel or ngrok) pointing at this studio, and open the studio through that address when you press Connect.",
         "Add the redirect address shown below, then paste the Client key and Client secret here.",
         "Add your TikTok account under \"Target users\" (sandbox) while the app is in development.",
     ],
     "notes": ["Until TikTok audits your app, every post is private (\"only me\"), whatever you choose here. Apply for the audit in the developer portal when you are ready."]},
    {"id": "x", "name": "X (Twitter)", "status": "soon", "makes": [], "steps": [], "notes": ["Planned. X charges for posting through its API."]},
    {"id": "linkedin", "name": "LinkedIn", "status": "soon", "makes": [], "steps": [], "notes": ["Planned."]},
    {"id": "pinterest", "name": "Pinterest", "status": "soon", "makes": [], "steps": [], "notes": ["Planned."]},
]
PLATFORM_OF = {"instagram": "meta", "facebook": "meta", "tiktok": "tiktok"}


class NeedsLogin(youtube.NeedsLogin):
    """The saved login stopped working: connect that account again."""


def _req(method: str, url: str, **kw: Any) -> httpx.Response:
    kw.setdefault("timeout", 60)
    return httpx.request(method, url, **kw)


def _err(r: httpx.Response) -> str:
    try:
        j = r.json()
        e = j.get("error")
        if isinstance(e, dict):
            return str(e.get("message") or e.get("error_user_msg") or e)[:240]
        return str(e or j.get("message") or r.text)[:240]
    except Exception:  # noqa: BLE001
        return r.text[:240] or f"HTTP {r.status_code}"


# ---------- storage ----------
def _soc(a: dict) -> dict:
    s = a.setdefault("social", {})
    s.setdefault("clients", {})
    s.setdefault("accounts", {})
    s.setdefault("pending", {})
    return s


def set_client(platform: str, key: str, secret: str) -> None:
    if platform not in {p["id"] for p in PLATFORMS if p["status"] == "ready"}:
        raise ValueError("Unknown platform.")
    if len(key.strip()) < 5 or len(secret.strip()) < 8:
        raise ValueError("That does not look like a real key and secret.")
    a = store.accounts()
    _soc(a)["clients"][platform] = {"id": key.strip(), "secret": secret.strip()}
    store.save_accounts(a)


def has_client(platform: str) -> bool:
    c = _soc(store.accounts())["clients"].get(platform) or {}
    return bool(c.get("id") and c.get("secret"))


def redirect_uri(platform: str, origin: str) -> str:
    return origin.rstrip("/") + f"/studio-api/autoclip/social/{platform}/callback"


def is_social(aid: str) -> bool:
    return aid.split(":", 1)[0] in PLATFORM_OF and ":" in aid


def accounts() -> list[dict]:
    """What the page may see about each account: never a token."""
    out = []
    for a in _soc(store.accounts())["accounts"].values():
        out.append({"id": a["id"], "platform": a["platform"], "title": a.get("title") or a["id"], "thumb": a.get("thumb", ""), "subs": a.get("subs"),
                    "connected": a.get("connected"), "needs_login": bool(a.get("needs_login")), "via": a.get("via", "")})
    return out


def platforms(origin: str = "") -> list[dict]:
    accs = accounts()
    res = []
    for p in PLATFORMS:
        mine = [a for a in accs if PLATFORM_OF.get(a["platform"]) == p["id"]]
        res.append(p | {"has_client": has_client(p["id"]) if p["status"] == "ready" else False, "accounts": mine,
                        "redirect": redirect_uri(p["id"], origin) if origin and p["status"] == "ready" else ""})
    return res


def disconnect(aid: str) -> bool:
    a = store.accounts()
    s = _soc(a)
    gone = s["accounts"].pop(aid, None)
    if gone:
        store.save_accounts(a)
    return bool(gone)


# ---------- signing in ----------
def auth_url(platform: str, origin: str) -> str:
    a = store.accounts()
    s = _soc(a)
    c = s["clients"].get(platform) or {}
    if not (c.get("id") and c.get("secret")):
        raise RuntimeError("Paste the app key and secret first.")
    state = secrets.token_urlsafe(24)
    s["pending"] = {k: v for k, v in s["pending"].items() if time.time() - v["t"] < 900}
    s["pending"][state] = {"platform": platform, "redirect": redirect_uri(platform, origin), "t": time.time(), "origin": origin.rstrip("/")}
    store.save_accounts(a)
    redir = s["pending"][state]["redirect"]
    if platform == "meta":
        q = {"client_id": c["id"], "redirect_uri": redir, "state": state, "scope": ",".join(META_SCOPES), "response_type": "code"}
        return FB_AUTH + "?" + urllib.parse.urlencode(q)
    if platform == "tiktok":
        q = {"client_key": c["id"], "redirect_uri": redir, "state": state, "scope": ",".join(TT_SCOPES), "response_type": "code"}
        return TT_AUTH + "?" + urllib.parse.urlencode(q)
    raise RuntimeError("Not available yet.")


def finish(platform: str, code: str, state: str) -> dict:
    a = store.accounts()
    s = _soc(a)
    pend = s["pending"].pop(state, None)
    if not pend or pend.get("platform") != platform or time.time() - pend["t"] > 900:
        raise RuntimeError("That sign-in link has expired or is not from this studio. Press Connect again.")
    store.save_accounts(a)
    c = s["clients"][platform]
    added = _finish_meta(c, code, pend["redirect"]) if platform == "meta" else _finish_tiktok(c, code, pend["redirect"])
    a = store.accounts()
    s = _soc(a)
    for acc in added:
        old = s["accounts"].get(acc["id"]) or {}
        s["accounts"][acc["id"]] = old | acc | {"connected": store.now(), "needs_login": False}
    store.save_accounts(a)
    return {"added": [x["id"] for x in added], "titles": [x["title"] for x in added]}


def _finish_meta(c: dict, code: str, redirect: str) -> list[dict]:
    r = _req("GET", f"{FB_API}/oauth/access_token", params={"client_id": c["id"], "client_secret": c["secret"], "redirect_uri": redirect, "code": code})
    if r.status_code != 200:
        raise RuntimeError("Meta refused the sign-in: " + _err(r))
    short = r.json()["access_token"]
    r = _req("GET", f"{FB_API}/oauth/access_token", params={"grant_type": "fb_exchange_token", "client_id": c["id"], "client_secret": c["secret"], "fb_exchange_token": short})
    user = r.json().get("access_token", short) if r.status_code == 200 else short          # page tokens made from a long-lived user token do not expire
    r = _req("GET", f"{FB_API}/me/accounts", params={"access_token": user, "limit": 100,
             "fields": "id,name,access_token,picture{url},followers_count,instagram_business_account{id,username,profile_picture_url,followers_count}"})
    if r.status_code != 200:
        raise RuntimeError("Could not list your Facebook Pages: " + _err(r))
    out: list[dict] = []
    for pg in r.json().get("data") or []:
        out.append({"id": f"facebook:{pg['id']}", "platform": "facebook", "title": pg.get("name") or pg["id"], "thumb": ((pg.get("picture") or {}).get("data") or {}).get("url", ""),
                    "subs": pg.get("followers_count"), "token": pg["access_token"], "remote": pg["id"]})
        ig = pg.get("instagram_business_account")
        if ig:
            out.append({"id": f"instagram:{ig['id']}", "platform": "instagram", "title": "@" + (ig.get("username") or ig["id"]), "thumb": ig.get("profile_picture_url", ""),
                        "subs": ig.get("followers_count"), "token": pg["access_token"], "remote": ig["id"], "via": pg.get("name") or ""})
    if not out:
        raise RuntimeError("That login manages no Facebook Pages. Create or get access to a Page (and link your Instagram professional account to it), then connect again.")
    return out


def _finish_tiktok(c: dict, code: str, redirect: str) -> list[dict]:
    r = _req("POST", f"{TT_API}/oauth/token/", data={"client_key": c["id"], "client_secret": c["secret"], "code": code, "grant_type": "authorization_code", "redirect_uri": redirect},
             headers={"Content-Type": "application/x-www-form-urlencoded"})
    j = r.json() if r.status_code == 200 else {}
    if not j.get("access_token"):
        raise RuntimeError("TikTok refused the sign-in: " + (j.get("error_description") or _err(r)))
    who = _req("GET", f"{TT_API}/user/info/", params={"fields": "open_id,display_name,avatar_url"}, headers={"Authorization": "Bearer " + j["access_token"]})
    u = ((who.json().get("data") or {}).get("user") or {}) if who.status_code == 200 else {}
    oid = u.get("open_id") or j.get("open_id")
    return [{"id": f"tiktok:{oid}", "platform": "tiktok", "title": u.get("display_name") or "TikTok", "thumb": u.get("avatar_url", ""), "token": j["access_token"],
             "refresh": j.get("refresh_token"), "expires": time.time() + int(j.get("expires_in", 86400)) - 120, "remote": oid}]


def _token(aid: str) -> dict:
    a = store.accounts()
    s = _soc(a)
    acc = s["accounts"].get(aid)
    if not acc:
        raise RuntimeError("That account is not connected.")
    if acc["platform"] == "tiktok" and acc.get("expires", 0) < time.time():
        c = s["clients"].get("tiktok") or {}
        r = _req("POST", f"{TT_API}/oauth/token/", data={"client_key": c.get("id"), "client_secret": c.get("secret"), "grant_type": "refresh_token", "refresh_token": acc.get("refresh")},
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
        j = r.json() if r.status_code == 200 else {}
        if not j.get("access_token"):
            acc["needs_login"] = True
            store.save_accounts(a)
            raise NeedsLogin(f"TikTok no longer accepts the saved login for {acc.get('title')}. Connect it again in Connections.")
        acc.update(token=j["access_token"], refresh=j.get("refresh_token") or acc.get("refresh"), expires=time.time() + int(j.get("expires_in", 86400)) - 120, needs_login=False)
        store.save_accounts(a)
    return acc


def _login_lost(aid: str, msg: str) -> NeedsLogin:
    a = store.accounts()
    acc = _soc(a)["accounts"].get(aid)
    if acc:
        acc["needs_login"] = True
        store.save_accounts(a)
    return NeedsLogin(msg)


def caption(title: str, description: str, tags: list[str] | None, limit: int = 2200) -> str:
    tg = " ".join("#" + "".join(ch for ch in t.lstrip("#") if ch.isalnum()) for t in (tags or []) if t.strip())[:300]
    parts = [youtube.clean_text(title, 150)]
    d = (description or "").strip()
    if d:
        parts.append(d)
    if tg:
        parts.append(tg)
    return "\n\n".join(parts)[:limit]


# ---------- posting ----------
def publish(aid: str, path: str, title: str, description: str = "", privacy: str = "private", tags: list[str] | None = None, publish_at: float | None = None) -> dict:
    """Post one finished clip. publish_at (unix time) is honoured by Facebook only: Meta then publishes it itself. Returns {"id": remote id, "url": link or None}."""
    f = Path(path)
    if not f.is_file():
        raise RuntimeError("The clip's file is missing.")
    acc = _token(aid)
    kind = acc["platform"]
    if kind == "instagram":
        return _post_instagram(aid, acc, f, caption(title, description, tags))
    if kind == "facebook":
        return _post_facebook(aid, acc, f, title, caption("", description, tags).strip(), privacy, publish_at)
    if kind == "tiktok":
        return _post_tiktok(aid, acc, f, caption(title, "", tags, 2000), privacy)
    raise RuntimeError("Unknown account type.")


def _graph_fail(aid: str, r: httpx.Response, what: str) -> RuntimeError:
    msg = _err(r)
    expired = '"code": 190' in r.text or '"code":190' in r.text or ("OAuthException" in r.text and "token" in r.text.lower())
    if r.status_code == 401 or expired:
        return _login_lost(aid, f"Meta no longer accepts the saved login. Connect it again in Connections. ({msg})")
    return RuntimeError(f"{what}: {msg}")


def _post_facebook(aid: str, acc: dict, f: Path, title: str, desc: str, privacy: str, publish_at: float | None = None) -> dict:
    data = {"access_token": acc["token"], "title": youtube.clean_text(title, 100), "description": desc[:5000]}
    if privacy != "public":
        data["published"] = "false"                              # private = saved on the Page, not shown
    elif publish_at:
        data.update(published="false", scheduled_publish_time=str(int(max(publish_at, time.time() + 11 * 60))))     # Meta wants 10 minutes to 75 days ahead
    with f.open("rb") as fh:
        r = _req("POST", f"{FB_VIDEO}/{acc['remote']}/videos", data=data, files={"source": (f.name, fh, "video/mp4")}, timeout=1800)
    if r.status_code != 200:
        raise _graph_fail(aid, r, "Facebook refused the video")
    vid = r.json().get("id")
    return {"id": str(vid), "url": f"https://www.facebook.com/{acc['remote']}/videos/{vid}" if privacy == "public" and not publish_at else None}


def _post_instagram(aid: str, acc: dict, f: Path, cap: str) -> dict:
    tok, ig = acc["token"], acc["remote"]
    r = _req("POST", f"{FB_API}/{ig}/media", data={"media_type": "REELS", "upload_type": "resumable", "caption": cap, "share_to_feed": "true", "access_token": tok})
    if r.status_code != 200 or not r.json().get("id"):
        raise _graph_fail(aid, r, "Instagram would not start the upload")
    cid = r.json()["id"]
    size = f.stat().st_size
    with f.open("rb") as fh:
        up = _req("POST", f"{IG_UPLOAD}/{cid}", content=fh, headers={"Authorization": "OAuth " + tok, "offset": "0", "file_size": str(size)}, timeout=1800)
    if up.status_code != 200:
        raise _graph_fail(aid, up, "Instagram refused the video")
    for _ in range(60):                                          # wait for Instagram to finish processing (up to about 5 minutes)
        st = _req("GET", f"{FB_API}/{cid}", params={"fields": "status_code,status", "access_token": tok})
        code = (st.json().get("status_code") if st.status_code == 200 else "") or ""
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError("Instagram could not process the video: " + str(st.json().get("status") or code)[:200] + " (Reels must be 3-90 s, vertical, MP4.)")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram is still processing the video. Check the account before you retry so it is not posted twice.")
    pub = _req("POST", f"{FB_API}/{ig}/media_publish", data={"creation_id": cid, "access_token": tok})
    if pub.status_code != 200:
        raise _graph_fail(aid, pub, "Instagram would not publish")
    mid = pub.json().get("id")
    link = None
    try:
        pl = _req("GET", f"{FB_API}/{mid}", params={"fields": "permalink", "access_token": tok})
        link = pl.json().get("permalink") if pl.status_code == 200 else None
    except Exception:  # noqa: BLE001
        pass
    return {"id": str(mid), "url": link}


def _post_tiktok(aid: str, acc: dict, f: Path, title: str, privacy: str) -> dict:
    size = f.stat().st_size
    if size > 64 * 1024 * 1024:
        raise RuntimeError("TikTok upload here is limited to 64 MB per clip.")
    level = "PUBLIC_TO_EVERYONE" if privacy == "public" else "SELF_ONLY"
    h = {"Authorization": "Bearer " + acc["token"], "Content-Type": "application/json; charset=UTF-8"}
    r = _req("POST", f"{TT_API}/post/publish/video/init/", headers=h, json={
        "post_info": {"title": title[:2000], "privacy_level": level, "disable_duet": False, "disable_comment": False, "disable_stitch": False},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size, "total_chunk_count": 1}})
    j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    err = j.get("error") or {}
    if r.status_code != 200 or err.get("code") not in (None, "ok"):
        if err.get("code") in ("access_token_invalid", "scope_not_authorized"):
            raise _login_lost(aid, "TikTok no longer accepts the saved login. Connect it again in Connections.")
        raise RuntimeError("TikTok refused the post: " + str(err.get("message") or _err(r))[:240])
    d = j["data"]
    with f.open("rb") as fh:
        up = _req("PUT", d["upload_url"], content=fh, headers={"Content-Type": "video/mp4", "Content-Length": str(size), "Content-Range": f"bytes 0-{size - 1}/{size}"}, timeout=1800)
    if up.status_code not in (200, 201, 206):
        raise RuntimeError("TikTok refused the video file: " + _err(up))
    for _ in range(40):
        time.sleep(3)
        st = _req("POST", f"{TT_API}/post/publish/status/fetch/", headers=h, json={"publish_id": d["publish_id"]})
        data = (st.json().get("data") or {}) if st.status_code == 200 else {}
        s = data.get("status")
        if s == "PUBLISH_COMPLETE":
            ids = data.get("publicaly_available_post_id") or data.get("publicly_available_post_id") or []
            return {"id": str(ids[0] if ids else d["publish_id"]), "url": None}
        if s == "FAILED":
            raise RuntimeError("TikTok could not publish: " + str(data.get("fail_reason") or "unknown reason") + (" (An unaudited app can only post private videos.)" if level != "SELF_ONLY" else ""))
    return {"id": d["publish_id"], "url": None}
