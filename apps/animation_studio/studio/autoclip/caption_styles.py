"""The caption style library (about 80 looks). Each entry is plain data; captions.py draws it.

Keys (all optional except label and font):
  upper, italic, size (share of the frame height), text / hi (colours #RRGGBB, hi may be "cycle"), outline, out (outline colour), shadow,
  words (per caption), anim (see captions.ANIMS),
  layout: "line" | "two" (two lines) | "each" (one word per line) | "cascade" (one word per line, each smaller) |
          "top" / "mid" / "bottom" (the key word big on its own line, above / between / below the rest) | "inline" (the key word bigger, same line)
  kw / rest: colour of the key word / the other words in key-word layouts;  kw_font, kw_italic, kw_upper, kw_scale, rest_scale, rest_font
  box: colour of a box behind the WHOLE line;  tiles: [colours] of a box behind EACH word (tile_text: their text colour);  hi_box: box behind the spoken word
  underline, dim (0-255: how faded the words not being said are), blur (blur of those words), glow (colour), echo, glitch, spacing, hi_font, hi_italic
The key word is the longest word of the caption (the one that carries the meaning), so it stays put while the words are said."""
from __future__ import annotations

from typing import Any

YEL, WHT, RED, GRN, CYN, PNK, GLD, ORG, PUR, BLK = "#FFE000", "#FFFFFF", "#FF3030", "#7AFF40", "#00E6FF", "#FF2D78", "#E8B84A", "#FF8A00", "#B46BFF", "#000000"
BASE: dict[str, Any] = {"font": "Poppins", "upper": False, "size": 0.047, "text": WHT, "hi": YEL, "outline": 4, "shadow": 2, "words": 3, "anim": "none", "layout": "line"}


def S(label: str, **kw: Any) -> dict[str, Any]:
    return {**BASE, "label": label, **kw}


STYLES: dict[str, dict[str, Any]] = {
    # ---- the first set ----
    "bounce": S("Bounce", anim="bounce"),
    "pop": S("Pop: colour moves every word", font="Montserrat Black", upper=True, size=0.052, hi="cycle", outline=5, anim="pop"),
    "hype": S("Hype", font="Montserrat Black", upper=True, size=0.05, hi=RED, outline=5),
    "clean": S("Clean", size=0.045, hi="#A0E0FF", outline=3, shadow=1),
    "karaoke": S("Karaoke fill", size=0.048, words=4, anim="karaoke"),
    "boxed": S("Word box", font="Montserrat ExtraBold", upper=True, size=0.048, hi_box=YEL, hi="#111111", shadow=2, anim="pop"),
    "gaming": S("Gaming", font="Bangers", upper=True, size=0.06, hi=GRN, outline=6, shadow=3, anim="shake"),
    "word": S("One word", font="Anton", upper=True, size=0.075, outline=6, shadow=3, words=1, anim="zoom"),
    "comic": S("Comic", font="Luckiest Guy", upper=True, size=0.05, text=YEL, hi=WHT, outline=6, shadow=3, words=2, anim="bounce"),
    "neon": S("Neon glow", font="Montserrat ExtraBold", size=0.048, hi=CYN, outline=3, shadow=0, anim="pulse", glow=CYN),
    "marker": S("Marker", font="Permanent Marker", size=0.05, hi=RED, anim="slide"),
    "serif": S("Editorial serif", font="DM Serif Display", size=0.05, hi=GLD, outline=3, anim="fade", layout="inline", kw=YEL, rest=WHT, kw_italic=True, kw_scale=1.35, rest_scale=0.8),
    "panel": S("Panel", size=0.044, words=4, outline=0, shadow=0, box="#000000B0", anim="fade"),
    "typewriter": S("Typewriter", font="Oswald", upper=True, size=0.055, words=4, anim="typewriter"),
    "impact": S("Impact", font="Bebas Neue", upper=True, size=0.072, outline=5, shadow=3, anim="elastic"),
    "desi": S("Desi (Hindi + English)", font="Baloo 2 ExtraBold", size=0.05, outline=5, anim="bounce"),
    # ---- clean and bold ----
    "cinematic": S("Cinematic", size=0.036, outline=2, shadow=3, anim="fade"),
    "karaoke_pop": S("Karaoke pop", size=0.046, anim="pop"),
    "bold_impact": S("Bold impact", font="Montserrat Black", upper=True, size=0.05, box="#000000C0", outline=0, shadow=0, layout="two"),
    "punch_box": S("Punch box", font="Montserrat Black", upper=True, size=0.058, box="#000000D0", outline=0, shadow=0, layout="two", anim="pop"),
    "clean_yellow": S("Clean yellow", size=0.046, outline=3),
    "neon_glow": S("Neon soft", font="Montserrat ExtraBold", size=0.048, text="#DFFBFF", hi=YEL, outline=2, shadow=0, glow="#00B4FF", layout="two"),
    "underline_pop": S("Underline pop", size=0.048, hi=WHT, underline=True, layout="two", anim="pop"),
    "documentary": S("Documentary", font="Inter ExtraBold", size=0.032, outline=2, words=4),
    "hormozi": S("Big bold two-line", font="Montserrat Black", size=0.058, outline=5, shadow=3, layout="two", anim="bounce"),
    "creator_white": S("Creator white", size=0.05, hi=GLD, outline=3, shadow=4, layout="two"),
    "anton_impact": S("Anton impact", font="Anton", upper=True, size=0.07, outline=5, shadow=3, layout="two"),
    "brand_block": S("Brand block", size=0.046, text="#111111", hi="#C81E1E", box="#FFD000E8", outline=0, shadow=0, layout="two"),
    "keyword_pop": S("Keyword pop", size=0.05, layout="two", anim="pop"),
    "outline_punch": S("Outline punch", font="Montserrat Black", upper=True, size=0.056, outline=7, shadow=0, layout="two"),
    "word_reveal": S("Word reveal", size=0.05, words=2, anim="typewriter"),
    "word_tiles": S("Word tiles", size=0.046, tiles=["#262626E0"], tile_text=WHT, outline=0, shadow=0, layout="two"),
    "sunset": S("Sunset", font="Montserrat Black", upper=True, size=0.054, text="#FF8A80", hi="#FFD166", outline=0, shadow=3, layout="two"),
    "sticker": S("Sticker", font="Montserrat Black", upper=True, size=0.056, text="#111111", hi="#111111", out="#FFFFFF", outline=8, shadow=4, layout="two"),
    # ---- editorial ----
    "editorial_scale": S("Editorial scale", font="Inter ExtraBold", size=0.05, layout="mid", kw_font="DM Serif Display", kw=YEL, rest=WHT, kw_scale=1.6, rest_scale=0.55, outline=2),
    "broadsheet": S("Broadsheet", font="Playfair Display", upper=True, size=0.05, layout="top", kw=YEL, rest=WHT, kw_scale=1.3, rest_scale=0.55, spacing=4, outline=2),
    "plate_keyword": S("Plate keyword", size=0.05, layout="inline", kw=YEL, rest=WHT, kw_scale=1.4, rest_scale=0.7, box="#00000099", outline=0, shadow=0),
    "editorial_column": S("Editorial column", font="Inter ExtraBold", size=0.05, layout="mid", kw_font="DM Serif Display", kw=YEL, rest=WHT, kw_scale=1.5, rest_scale=0.5, outline=2),
    "editorial_mono": S("Editorial mono", font="JetBrains Mono", upper=True, size=0.05, layout="bottom", kw_font="Oswald", kw=YEL, rest=WHT, kw_scale=1.3, rest_scale=0.45, spacing=4, outline=2),
    "editorial_italic": S("Editorial italic", font="DM Serif Display", size=0.05, layout="inline", kw=YEL, rest=WHT, kw_italic=True, kw_scale=1.4, rest_scale=0.7, italic=True, outline=2),
    "masthead": S("Masthead", font="Playfair Display", upper=True, size=0.05, layout="mid", kw=YEL, rest=WHT, kw_scale=1.6, rest_scale=0.45, spacing=3, outline=2),
    # ---- motion ----
    "blur_switch": S("Blur switch", size=0.05, hi=WHT, blur=4, dim=110, layout="two"),
    "fade_stack": S("Fade stack", size=0.05, hi=WHT, dim=150, layout="two"),
    "echo_trail": S("Echo trail", font="Anton", upper=True, size=0.06, echo=True),
    "glitch": S("Glitch", font="Anton", upper=True, size=0.06, glitch=True, anim="shake"),
    "karaoke_soft": S("Karaoke soft", size=0.048, text="#9A9A9A", hi=WHT, layout="two", anim="karaoke"),
    "bounce_soft": S("Bounce soft", size=0.05, layout="two", anim="bounce"),
    "bounce_hard": S("Bounce hard", font="Anton", upper=True, size=0.064, anim="elastic"),
    "slide_in": S("Slide in", size=0.05, layout="two", anim="slide"),
    "blur_scroller": S("Blur scroller", size=0.05, hi=WHT, blur=3, dim=90, layout="two", anim="slide"),
    "word_boxes": S("Word boxes", font="Bangers", upper=True, size=0.056, tiles=[PNK, YEL, WHT], tile_text="#111111", outline=0, shadow=2, anim="pop"),
    "word_boxes_mono": S("Word boxes mono", size=0.046, tiles=["#1E1E1EE8"], tile_text=WHT, outline=0, shadow=0, layout="two"),
    "sans_serif": S("Sans + serif", font="Anton", upper=True, size=0.06, hi_font="DM Serif Display", hi_italic=True, layout="two"),
    "panel_serif": S("Panel serif", font="DM Serif Display", size=0.05, box="#000000B0", outline=0, shadow=0, layout="mid", kw=YEL, rest=WHT, kw_scale=1.25, rest_scale=0.75),
    "clean_impact": S("Clean impact", font="Anton", upper=True, size=0.062, anim="pop"),
    "neon_punch": S("Neon punch", font="Anton", upper=True, size=0.064, text="#E8F6FF", glow="#2F6BFF", outline=3, shadow=0, layout="two"),
    "boxed_punch": S("Boxed punch", font="Montserrat Black", upper=True, size=0.056, layout="each"),
    "bold_duo": S("Bold duo", font="Anton", upper=True, size=0.066, layout="two", anim="elastic"),
    "golden_frame": S("Golden frame", font="DM Serif Display", size=0.054, hi=GLD, outline=3, layout="two", anim="fade"),
    "signature_flow": S("Signature flow", font="DM Serif Display", size=0.05, hi_font="Pacifico", hi=YEL, outline=3),
    "aqua_edge": S("Aqua edge", font="Montserrat Black", upper=True, size=0.054, out="#00A8FF", outline=5, glow="#00C8FF", layout="two"),
    "purple_wave": S("Purple wave", size=0.05, hi=PUR, hi_italic=True, layout="two", anim="bounce"),
    "flame_bold": S("Flame bold", font="Anton", upper=True, size=0.064, text="#FFD23F", hi=WHT, out="#FF3B00", outline=5, glow="#FF5A00"),
    "comic_burst": S("Comic burst", font="Bangers", upper=True, size=0.058, tiles=[YEL, "#2F7BFF", PNK], tile_text="#111111", outline=0, shadow=3, anim="elastic"),
    "karaoke_classic": S("Karaoke", font="Inter ExtraBold", size=0.046, text="#BDBDBD", hi=YEL, anim="karaoke", words=4),
    "podcast_sub": S("Podcast subtitle", size=0.034, bold=False, words=10, layout="twokw", kw=YEL, rest=WHT, box="#00000099", outline=0, shadow=0, anim="none"),
    "clean_card": S("Clean card", size=0.04, box="#000000A0", outline=0, shadow=0, anim="fade"),
    "podcast": S("Podcast", size=0.032, outline=2, words=4),
    "documentary_fade": S("Documentary fade", font="Inter ExtraBold", size=0.032, outline=2, words=4, anim="fade"),
    "arcade": S("Arcade", font="Anton", upper=True, size=0.062, outline=7, shadow=4, anim="pulse"),
    # ---- platform looks ----
    "tiktok_viral": S("TikTok style", size=0.056, words=2, anim="pop"),
    "instagram_viral": S("Reels style", size=0.046, layout="two", anim="bounce"),
    "capcut_trending": S("CapCut style", font="Montserrat Black", size=0.052, layout="two", anim="bounce"),
    "cinema": S("Cinema", font="Inter ExtraBold", upper=True, size=0.028, spacing=5, outline=1, shadow=3, words=4, anim="fade"),
    "minimal": S("Minimal", size=0.028, outline=0, shadow=2, words=4),
    "editorial": S("Editorial", font="Inter ExtraBold", upper=True, size=0.032, spacing=3, outline=1, layout="two"),
    "stacked": S("Stacked", font="Montserrat Black", upper=True, size=0.05, words=2),
    "whisper": S("Whisper", font="Inter ExtraBold", size=0.036, hi=WHT, dim=120, outline=1, shadow=2),
    # ---- big key word over small words ----
    "premium_open": S("Key word on top", layout="top", kw=YEL, rest=WHT, kw_scale=1.8, rest_scale=0.55),
    "premium_centre": S("Key word, centred", font="Montserrat Black", layout="top", kw=YEL, rest=WHT, kw_scale=1.7, rest_scale=0.55),
    "premium_land": S("Key word below", layout="bottom", kw=YEL, rest=WHT, kw_scale=1.7, rest_scale=0.5),
    "premium_shout": S("Key word shout", font="Montserrat Black", layout="top", kw_upper=True, kw=YEL, rest=WHT, kw_scale=1.7, rest_scale=0.5),
    "premium_impact": S("Key word impact", font="Anton", layout="top", kw_upper=True, kw=YEL, rest=WHT, kw_scale=2.0, rest_scale=0.55),
    "premium_stack": S("Shrinking stack", layout="cascade", kw=YEL, rest=WHT, kw_scale=1.6, rest_scale=0.6),
    "opportunity": S("Middle word big", layout="mid", kw=WHT, rest=WHT, kw_scale=1.7, rest_scale=0.5),
    "one_move": S("Key word caps", font="Montserrat Black", layout="top", kw_upper=True, kw=YEL, rest=WHT, kw_scale=1.6, rest_scale=0.5),
    "the_difference": S("Key word cascade", layout="cascade", kw=YEL, rest=WHT, kw_scale=1.5, rest_scale=0.55),
    "learn": S("Serif key word", layout="top", kw_font="DM Serif Display", kw_italic=True, kw=YEL, rest=WHT, kw_scale=1.8, rest_scale=0.5),
    "missing": S("White key word", font="Montserrat Black", layout="top", kw_upper=True, kw=WHT, rest=WHT, kw_scale=1.7, rest_scale=0.5),
    "shorter": S("Caps in the middle", font="Montserrat Black", layout="mid", kw_upper=True, kw=YEL, rest=WHT, kw_scale=1.6, rest_scale=0.5),
    "the_logic": S("Serif in the middle", layout="mid", kw_font="DM Serif Display", kw_italic=True, kw=WHT, rest=YEL, kw_scale=1.6, rest_scale=0.5),
    "nobody_talks": S("Yellow caps on top", font="Montserrat Black", layout="top", kw_upper=True, kw=YEL, rest=WHT, kw_scale=1.6, rest_scale=0.6),
    "simplify": S("Yellow middle", layout="mid", kw=YEL, rest=WHT, kw_scale=1.5, rest_scale=0.5),
    "look_at": S("Serif yellow on top", layout="top", kw_font="DM Serif Display", kw_italic=True, kw=YEL, rest=WHT, kw_scale=1.7, rest_scale=0.6),
    "explain": S("Caps middle, yellow", font="Montserrat Black", layout="mid", kw_upper=True, kw=YEL, rest=WHT, kw_scale=1.5, rest_scale=0.5),
    "numeral": S("Big serif, yellow under", layout="top", kw_font="DM Serif Display", kw=WHT, rest=YEL, kw_scale=2.0, rest_scale=0.55),
    "wrong_place": S("Key word below, yellow", layout="bottom", kw=YEL, rest=WHT, kw_scale=1.5, rest_scale=0.5),
    "beginners": S("Yellow top, bold under", layout="top", kw=YEL, rest=WHT, kw_scale=1.5, rest_scale=0.6),
}
