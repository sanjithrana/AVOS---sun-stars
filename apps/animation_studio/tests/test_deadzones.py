"""No clip from the intro, the end credits, or a stretch where nobody talks."""
from studio.autoclip import hype


def talk(t0, t1, rate=2.5):
    n = int((t1 - t0) * rate)
    return [{"w": "word", "s": t0 + i / rate, "e": t0 + i / rate + 0.3} for i in range(n)]


def test_intro_credits_and_music_are_dead():
    total = 3000.0                                                       # a 50-minute show
    words = talk(20, 1500) + [{"w": "[Music]", "s": t, "e": t + 1} for t in range(1500, 1700, 5)] + talk(1700, 2870)
    z = hype.dead_zones(total, words, True)
    dead = lambda t: any(a <= t < b for a, b in z)                       # noqa: E731
    assert dead(5) and dead(2950) and dead(1600) and not dead(600) and not dead(2000)
    curve = [1.0] * 3000
    m = hype.mask(curve, 0.0, z)
    assert m[2950] == 0.0 and m[1600] == 0.0 and m[600] == 1.0
    assert hype.speech_rate(words, 1550, 1650) == 0 and hype.speech_rate(words, 600, 640) > 2


def test_gameplay_keeps_quiet_action_and_short_videos_keep_their_ends():
    z = hype.dead_zones(3000.0, talk(0, 100), False)
    assert len(z) == 2                                                   # only intro and outro for gameplay
    assert hype.dead_zones(200.0, talk(0, 200), True) == []
