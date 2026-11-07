"""Article link → readable text, safely. Only public http(s) pages: every address is checked (also after each redirect),
size and time are capped, and nothing but text is kept."""
from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

MAX_BYTES = 1_500_000
MAX_REDIRECTS = 3
TIMEOUT = 12
UA = "Mozilla/5.0 (compatible; AVOS-Studio article reader)"


class ArticleError(ValueError):
    pass


def _check_host(host: str, port: int) -> None:
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as e:
        raise ArticleError(f"I couldn't find that website ({host}).") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ArticleError("That address points inside a private network, so I won't open it.")


def check_url(url: str) -> urllib.parse.ParseResult:
    u = urllib.parse.urlparse((url or "").strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise ArticleError("Paste a full web address that starts with http:// or https://")
    port = u.port or (443 if u.scheme == "https" else 80)
    if port not in (80, 443):
        raise ArticleError("Only normal web ports (80 and 443) are allowed.")
    if u.username or u.password:
        raise ArticleError("Addresses with a username or password aren't allowed.")
    _check_host(u.hostname, port)
    return u


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # noqa: ANN002, ANN003
        return None


def _get(url: str) -> tuple[str, bytes]:
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            r = opener.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            raise ArticleError(f"The website answered with an error ({e.code}).") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ArticleError("I couldn't open that page (it may be offline or blocking me).") from e
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            raise ArticleError("That link isn't a web page with text.")
        data = r.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ArticleError("That page is too large.")
        enc = re.search(r"charset=([\w-]+)", ctype)
        return (enc.group(1) if enc else "utf-8"), data
    raise ArticleError("Too many redirects.")


SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "iframe", "button", "template"}
BLOCK = {"p", "h1", "h2", "h3", "h4", "li", "blockquote"}


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.cur: list[str] = []
        self.kind = ""
        self.blocks: list[tuple[str, str]] = []
        self.title = ""
        self.og = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        if tag == "meta" and a.get("property") == "og:title" and a.get("content"):
            self.og = a["content"].strip()
        if tag == "title":
            self._in_title = True
        if tag in SKIP:
            self.skip += 1
        elif tag in BLOCK and not self.skip:
            self._flush()
            self.kind = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self.skip and self.kind:
            self.cur.append(data)

    def _flush(self) -> None:
        t = " ".join("".join(self.cur).split())
        if t and self.kind:
            self.blocks.append((self.kind, t))
        self.cur, self.kind = [], ""


def extract(html: str, url: str = "") -> dict:
    p = _Text()
    p.feed(html)
    p._flush()
    paras = [(k, t) for k, t in p.blocks if (k.startswith("h") and len(t) > 3) or len(t.split()) >= 8]
    title = next((t for k, t in paras if k == "h1"), "") or p.og or " ".join(p.title.split())
    text = "\n".join(("## " + t) if k.startswith("h") else t for k, t in paras)
    if len(text.split()) < 60:
        raise ArticleError("I couldn't find enough article text on that page.")
    return {"url": url, "title": title[:160], "text": text, "words": len(text.split())}


def fetch(url: str) -> dict:
    enc, data = _get(url)
    return extract(data.decode(enc, "replace"), url)


def excerpt(a: dict, max_chars: int = 3800) -> str:
    """What the script writer sees: the title and the start of the text, cut at a paragraph end (free AI tiers have small limits)."""
    text = a["text"]
    if len(text) > max_chars:
        text = text[:max_chars].rsplit("\n", 1)[0]
    return f"Title: {a['title']}\n{text}"
