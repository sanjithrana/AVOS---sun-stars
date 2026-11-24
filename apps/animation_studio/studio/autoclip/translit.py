"""Hindi in Devanagari -> Hinglish (Roman letters, the way people type it in comments: "kuchh nahi peeti", not "kucha nahī pītī").

Rules: each consonant carries an "a" unless a vowel sign, a virama or the end of the word removes it; the "a" in the middle of a word is
dropped where Hindi speakers drop it (between a vowel-carrying syllable and the next consonant + vowel: "samajhna", "kamra");
long vowels are written the common way (aa -> a at the end of short words is kept as "aa"? no: "aa" stays inside, the final "aa" is "a").
Words with no Devanagari are left exactly as they are."""
from __future__ import annotations

import re

V = {"अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ॲ": "e"}
M = {"ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e"}
C = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh",
     "ण": "n", "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n", "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r", "ल": "l",
     "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h", "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "d", "ढ़": "rh", "फ़": "f", "य़": "y"}
NUK = {"क": "q", "ख": "kh", "ग": "gh", "ज": "z", "ड": "d", "ढ": "rh", "फ": "f"}
VIRAMA, NUKTA, ANUSVARA, CHANDRA, VISARGA = "्", "़", "ं", "ँ", "ः"
DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
COMMON = {"है": "hai", "हैं": "hain", "में": "mein", "मैं": "main", "नहीं": "nahi", "क्या": "kya", "क्यों": "kyun", "यह": "yeh", "वह": "woh", "और": "aur",
          "हाँ": "haan", "हां": "haan", "भाई": "bhai", "यार": "yaar", "कुछ": "kuchh", "बहुत": "bahut", "अच्छा": "accha", "मुझे": "mujhe", "तुम": "tum",
          "आप": "aap", "हम": "hum", "था": "tha", "थी": "thi", "थे": "the", "को": "ko", "का": "ka", "की": "ki", "के": "ke", "से": "se", "पर": "par",
          "ने": "ne", "तो": "toh", "भी": "bhi", "ही": "hi", "जो": "jo", "एक": "ek", "अब": "ab", "सब": "sab", "कर": "kar", "रहा": "raha", "रही": "rahi",
          "गया": "gaya", "गई": "gayi", "दे": "de", "ले": "le", "चल": "chal", "बस": "bas", "लेकिन": "lekin", "मत": "mat", "पता": "pata"}
HAS = re.compile(r"[ऀ-ॿ]")


def _syllables(word: str) -> list[list[str]]:
    """[[consonant(s), vowel or '' (inherent a) or '-' (no vowel)], ...] plus marks attached to the vowel ('n' for a nasal)."""
    out: list[list[str]] = []
    i = 0
    while i < len(word):
        ch = word[i]
        if ch in C or (ch in NUK and i + 1 < len(word) and word[i + 1] == NUKTA):
            if i + 1 < len(word) and word[i + 1] == NUKTA:
                cons = NUK.get(ch, C.get(ch, ""))
                i += 1
            else:
                cons = C[ch]
            vow = ""
            j = i + 1
            if j < len(word) and word[j] in M:
                vow = M[word[j]]
                j += 1
            elif j < len(word) and word[j] == VIRAMA:
                vow = "-"
                j += 1
            nas = ""
            while j < len(word) and word[j] in (ANUSVARA, CHANDRA, VISARGA):
                nas += "n" if word[j] != VISARGA else "h"
                j += 1
            out.append([cons, vow, nas])
            i = j
        elif ch in V:
            nas = ""
            j = i + 1
            while j < len(word) and word[j] in (ANUSVARA, CHANDRA, VISARGA):
                nas += "n" if word[j] != VISARGA else "h"
                j += 1
            out.append(["", V[ch], nas])
            i = j
        else:
            out.append([ch, "-", ""])
            i += 1
    return out


def word_to_roman(w: str) -> str:
    if not HAS.search(w):
        return w
    lead = re.match(r"^[^\w\u0900-\u097F]*", w).group(0)
    tail = re.search(r"[^\w\u0900-\u097F]*$", w).group(0)
    core = w[len(lead): len(w) - len(tail)] if tail else w[len(lead):]
    if core in COMMON:
        return lead + COMMON[core] + tail
    sy = _syllables(core)
    n = len(sy)
    vow = [s[1] for s in sy]
    for k in range(n):                       # where the inherent "a" is not said
        if vow[k] != "":
            continue
        if k == n - 1 and n > 1:             # the last consonant: "kamal" not "kamala"
            vow[k] = "-"
        elif 0 < k < n - 1 and vow[k - 1] not in ("-",) and vow[k + 1] not in ("", "-") and sy[k][0] and sy[k + 1][0]:
            vow[k] = "-"                     # VC(a)CV -> VCCV: "samajhana" -> "samajhna"
    out = []
    for k, (cons, _, nas) in enumerate(sy):
        v = vow[k]
        v = "a" if v == "" else ("" if v == "-" else v)
        out.append(cons + v + nas)
    r = "".join(out)
    r = re.sub(r"aa$", "a", r) if len(r) > 4 else r      # final long a: "accha", "raha"
    r = r.replace("ee", "i") if r.endswith("ee") and len(r) > 3 else r
    r = re.sub(r"ee$", "i", r)
    return lead + r.translate(DIGITS) + tail


def to_roman(text: str) -> str:
    return " ".join(word_to_roman(w) for w in text.split())


def roman_words(words: list[dict]) -> list[dict]:
    return [{**w, "w": word_to_roman(w["w"])} for w in words]
