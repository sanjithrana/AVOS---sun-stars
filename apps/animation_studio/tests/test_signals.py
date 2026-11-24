"""The highlight engine's signal mix, comment timestamps, the 'why', and the caption line."""
from studio.autoclip import meta, pick, signals


def test_missing_signals_are_left_out_not_zero():
    one, used = signals.combine({"audio": [0.0, 0.8, 0.2], "chat": [], "comments": None}, 3)
    assert used == ["audio"] and abs(one[1] - 0.8) < 1e-9                     # audio alone carries the full weight
    two, used2 = signals.combine({"audio": [0.0, 0.8, 0.8], "visual": [0.0, 0.0, 0.9]}, 3)
    assert set(used2) == {"audio", "visual"} and two[2] > two[1]               # both peaking beats one


def test_comment_timestamps():
    assert signals.times_in("lmao 4:32 and 1:02:05 💀, not 12:345") == [272, 3725]
    curve = signals.comments_curve([{"text": "4:32 💀", "like_count": 900}, {"text": "4:30 bro", "like_count": 2}, {"text": "great video"}], 600)
    assert curve and max(range(len(curve)), key=curve.__getitem__) in range(272, 279) and curve[100] == 0
    assert signals.comments_curve([{"text": "only 1:00", "like_count": 5}], 600) == []    # one timestamp is not a signal


def test_why_ranks_what_fired():
    w = signals.why({"audio": [0.1] * 10 + [0.9] * 5, "visual": [0.5] * 15, "comments": [0.0] * 15}, 0.0, 8, 14)
    assert list(w)[:2] == ["audio", "visual"] and w["audio"] == 0.9


def test_no_highlight_n_titles_and_one_caption_line():
    t = pick.title_for("", 2, "INDIA'S GOT LATENT S2 EP9 ft. Raftaar, Balraj Ghai | Samay Raina", "funny moment")
    assert "Highlight" not in t and t.startswith("India's Got Latent S2 EP9") and "funny moment" in t and "😂" in t
    assert "Highlight" not in pick.title_for("", 1, "", None)
    clip = {"title": "He lost it", "description": "Highlight 2\\nSource: Some Channel https://youtu.be/x\\n#funny"}
    desc, tags = meta.build({**clip, "description": "Highlight 2\nSource: x\nHe really lost it on stage #funny"}, {"title": "show", "source": {"channel": "Some Channel", "url": "u"}})
    assert desc.startswith("He really lost it on stage") and "Source" not in desc and "Highlight" not in desc and "🎬" not in desc and "#" in desc
