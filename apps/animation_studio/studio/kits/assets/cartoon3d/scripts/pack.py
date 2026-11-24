#!/usr/bin/env python3
"""pack.py: builds ONE self-contained HTML player from a story file and a voiceover.

    python3 pack.py story.js [voice.mp3] [-o my-short.html] [--offline]

- story.js : your SHORT = {...} file (see references/engine.md)
- voice    : mp3 / wav / m4a. It is embedded, so the HTML plays and exports with the voice anywhere.
- --offline: also embeds three.js (bigger file, works with no internet at all)
- --words words.json: exact word timings [{text,start,end}] (ElevenLabs "with timestamps", Whisper). Optional:
  without them the player lines the script up with the pauses in the voice by itself.
Only uses the Python standard library.
"""
import base64, os, sys, re, json

ENGINE = ["paint.js", "core.js", "cast.js", "world.js", "timing.js", "audio.js", "round.js", "overlay.js", "rooms.js", "samples.js"]
HERE = os.path.dirname(os.path.abspath(__file__))
ENG = os.path.join(HERE, "..", "engine")

def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    out, offline, pos, words = None, False, [], None
    i = 0
    while i < len(args):
        if args[i] == "-o": out = args[i + 1]; i += 2; continue
        if args[i] == "--offline": offline = True; i += 1; continue
        if args[i] == "--words": words = args[i + 1]; i += 2; continue
        pos.append(args[i]); i += 1
    story = pos[0]; voice = pos[1] if len(pos) > 1 else None
    src = open(story, encoding="utf-8").read()
    if "SHORT" not in src: sys.exit("pack.py: the story file must define window.SHORT = {...}")
    title = (re.search(r'title\s*:\s*["\']([^"\']+)', src) or [None, "Cartoon Short"])[1]
    html = open(os.path.join(ENG, "player.html"), encoding="utf-8").read()
    eng = "\n".join(open(os.path.join(ENG, f), encoding="utf-8").read() for f in ENGINE)
    html = html.replace("/*TITLE*/", title)
    font = os.path.join(HERE, "..", "fonts", "Fredoka.ttf")   # caption font (SIL OFL), embedded so captions look the same everywhere
    css = ""
    if os.path.exists(font):
        css = "<style>@font-face{font-family:CapFont;font-weight:300 700;src:url(data:font/ttf;base64," + base64.b64encode(open(font, "rb").read()).decode() + ") format('truetype');}</style>"
    html = html.replace("<!--FONTS-->", css)
    sdir, samples = os.path.join(ENG, "sfx"), {}                # recorded crowd sounds (laugh, gasp, cheer…)
    if os.path.isdir(sdir):
        for f in sorted(os.listdir(sdir)):
            if f.endswith(".mp3"): samples[f[:-4]] = base64.b64encode(open(os.path.join(sdir, f), "rb").read()).decode()
    eng = "window.CS_SAMPLES = " + json.dumps(samples) + ";\n" + eng
    html = html.replace("<!--ENGINE-->", "<script>\n" + eng + "\n</script>")
    if voice:
        b = base64.b64encode(open(voice, "rb").read()).decode()
        html = html.replace("<!--VOICE-->", '<script>window.VOICE_B64 = "' + b + '";</script>')
    else:
        html = html.replace("<!--VOICE-->", "")
    if words:
        html = html.replace("<!--STORY-->", "<script>window.SHORT_WORDS = " + open(words, encoding="utf-8").read() + ";</script>\n<!--STORY-->")
    html = html.replace("<!--STORY-->", "<script>\n" + src + "\n</script>")
    html = html.replace("<!--PLAYER-->", "<script>\n" + open(os.path.join(ENG, "player.js"), encoding="utf-8").read() + "\n</script>")
    if offline:
        three = open(os.path.join(ENG, "three.min.js"), encoding="utf-8").read()
        html = re.sub(r'<script src="https://cdnjs[^"]+"></script>\s*<script>window.THREE[^<]+</script>', lambda m: "<script>" + three + "</script>", html)
    out = out or os.path.splitext(story)[0] + ".html"
    open(out, "w", encoding="utf-8").write(html)
    print("saved", out, "(%.1f MB)" % (os.path.getsize(out) / 1e6))

if __name__ == "__main__":
    main()
