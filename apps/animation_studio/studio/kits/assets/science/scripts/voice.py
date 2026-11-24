#!/usr/bin/env python3
"""voice.py: turns a script into a narration file + exact word timings (words.json). Python standard library only.

    python3 voice.py stories/my-story/script.txt                 # best free option on this computer
    python3 voice.py stories/my-story/script.txt --engine system --voice "Microsoft Zira Desktop"
    python3 voice.py stories/my-story/script.txt --engine elevenlabs [--voice VOICE_ID] [--model eleven_multilingual_v2]
    python3 voice.py stories/my-story/script.txt --list           # show the system voices

Engines
- system      Free, built into your computer. Windows: the Windows voices (with exact word timings).
              Mac: the `say` voices (no word timings: the player lines the script up with the pauses by itself).
              Good for drafts. For a channel, a real voice is better (your own, or ElevenLabs).
- elevenlabs  Natural AI voice with exact word timings. Needs your own key: set ELEVENLABS_API_KEY, or put a line
              ELEVENLABS_API_KEY=... in a file called keys.txt in the kit folder. Uses your ElevenLabs credits.
- your own voice: just record the script on your phone (quiet room, steady pace), save it as voice.mp3 / .m4a / .wav
              next to script.txt. No words.json needed.
Writes voice.wav or voice.mp3 and words.json next to the script. Free from Anylancer.com.
"""
import sys, os, re, json, base64, difflib, subprocess, tempfile, platform, urllib.request, wave

def norm(w): return re.sub(r"[^a-z0-9]+", "", w.lower().replace("’", "").replace("'", ""))
def tokens(script):   # the same word split the player uses
    script = re.sub(r"\*", "", script)
    return [t for t in re.split(r"\s+", script.replace("…", "… ").replace("—", "— ").replace("–", "– ")) if norm(t)]

def align(script, spoken):
    """spoken: [(text, start, end)] from the engine -> one timing per script word (numbers like 1730 vs 'seventeen thirty' are spread)."""
    toks = tokens(script); a = [norm(t) for t in toks]; b = [norm(s[0]) for s in spoken]
    out = [None] * len(toks)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1): out[i1 + k] = spoken[j1 + k][1:3]
        elif i2 > i1:
            s0 = spoken[j1][1] if j2 > j1 else (out[i1 - 1][1] if i1 and out[i1 - 1] else 0)
            s1 = spoken[j2 - 1][2] if j2 > j1 else (spoken[j1][1] if j1 < len(spoken) else s0 + .3)
            n = i2 - i1
            for k in range(n): out[i1 + k] = (s0 + (s1 - s0) * k / n, s0 + (s1 - s0) * (k + 1) / n)
    return [{"text": t, "start": round(o[0], 3), "end": round(o[1], 3)} for t, o in zip(toks, out)]

def plain(script): return re.sub(r"\*", "", script).replace("…", "... ").strip()

PS = r"""param([string]$in, [string]$out, [string]$voice, [int]$rate)
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
if ($voice) { $s.SelectVoice($voice) }
$s.Rate = $rate
$global:W = New-Object System.Collections.Generic.List[string]
$s.add_SpeakProgress({ param($o, $e) $global:W.Add(('{0}|{1:0.000}' -f $e.Text, $e.AudioPosition.TotalSeconds)) })
$s.SetOutputToWaveFile($out)
$s.Speak([IO.File]::ReadAllText($in))
$s.Dispose()
$global:W -join "`n"
"""
def system_voice(script, folder, voice=None, rate=0, list_only=False):
    osn = platform.system()
    if osn == "Windows":
        tmp = tempfile.mkdtemp(); ps = os.path.join(tmp, "v.ps1"); open(ps, "w", encoding="utf-8").write(PS)
        if list_only:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | % { $_.VoiceInfo.Name }"], capture_output=True, text=True)
            print(r.stdout); return
        txt = os.path.join(tmp, "s.txt"); open(txt, "w", encoding="utf-8").write(plain(script))
        out = os.path.join(folder, "voice.wav")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps, "-in", txt, "-out", out, "-voice", voice or "", "-rate", str(rate)], capture_output=True, text=True)
        if r.returncode or not os.path.exists(out): sys.exit("voice.py: the Windows voice failed:\n" + r.stderr)
        with wave.open(out) as w: dur = w.getnframes() / w.getframerate()
        rows = [l.split("|") for l in r.stdout.strip().splitlines() if "|" in l]
        spoken = [(t, float(s), float(rows[i + 1][1]) if i + 1 < len(rows) else dur) for i, (t, s) in enumerate(rows)]
        json.dump(align(script, spoken), open(os.path.join(folder, "words.json"), "w"), indent=0)
        print("saved", out, "and words.json (%.1f s, Windows voice)" % dur)
    elif osn == "Darwin":
        if list_only: subprocess.run(["say", "-v", "?"]); return
        out = os.path.join(folder, "voice.wav"); tmp = tempfile.mktemp(suffix=".txt"); open(tmp, "w", encoding="utf-8").write(plain(script))
        cmd = ["say", "-o", out, "--file-format=WAVE", "--data-format=LEI16@22050", "-f", tmp] + (["-v", voice] if voice else [])
        if subprocess.run(cmd).returncode: sys.exit("voice.py: `say` failed")
        print("saved", out, "(Mac voice; no words.json, the player lines up the script with the pauses)")
    else:
        sys.exit("voice.py: no free system voice on this OS. Record your own voice or use --engine elevenlabs.")

def key_from_files():
    k = os.environ.get("ELEVENLABS_API_KEY")
    if k: return k
    for p in [os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "keys.txt"), "keys.txt"]:
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.strip().startswith("ELEVENLABS_API_KEY="): return line.split("=", 1)[1].strip()
    return None

def eleven(script, folder, voice=None, model=None):
    k = key_from_files()
    if not k: sys.exit("voice.py: no ElevenLabs key. Set ELEVENLABS_API_KEY or put ELEVENLABS_API_KEY=... in keys.txt")
    voice = voice or "JBFqnCBsd6RMkjVDRZzb"   # a default ElevenLabs narrator voice; pick your own in the Voice Library
    body = json.dumps({"text": plain(script), "model_id": model or "eleven_multilingual_v2", "voice_settings": {"stability": .45, "similarity_boost": .75}}).encode()
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128", data=body, headers={"xi-api-key": k, "Content-Type": "application/json"})
    try: d = json.loads(urllib.request.urlopen(req, timeout=300).read())
    except Exception as e: sys.exit("voice.py: ElevenLabs request failed: %s" % e)
    out = os.path.join(folder, "voice.mp3"); open(out, "wb").write(base64.b64decode(d["audio_base64"]))
    al = d.get("alignment") or d.get("normalized_alignment"); ch, st, en = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    spoken, cur = [], None
    for c, s, e in zip(ch, st, en):
        if c.isspace():
            if cur: spoken.append(tuple(cur)); cur = None
        else:
            if not cur: cur = [c, s, e]
            else: cur[0] += c; cur[2] = e
    if cur: spoken.append(tuple(cur))
    json.dump(align(script, spoken), open(os.path.join(folder, "words.json"), "w"), indent=0)
    print("saved", out, "and words.json (ElevenLabs)")

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"): print(__doc__); return
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if "--list" in a: system_voice("", ".", list_only=True); return
    path = a[0]; script = open(path, encoding="utf-8").read(); folder = os.path.dirname(os.path.abspath(path))
    eng = opt("--engine", "auto")
    if eng == "auto": eng = "elevenlabs" if key_from_files() else "system"
    if eng == "elevenlabs": eleven(script, folder, opt("--voice"), opt("--model"))
    else: system_voice(script, folder, opt("--voice"), int(opt("--rate", 0)))

if __name__ == "__main__":
    main()
