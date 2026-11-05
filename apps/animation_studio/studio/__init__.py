"""AVOS Animation Studio: ReelMimic's workflow (reference video → style → plan → gated production → critic)
rebuilt in Python, with a local-first AI crew (Ollama) and a built-in 2D renderer."""


def _prefer_ipv4() -> None:
    """Docker Desktop (Windows) often has no IPv6 route: a site that lists an IPv6 address first fails with
    "[Errno 101] Network is unreachable". Try the IPv4 addresses first (nothing is removed, IPv6 is still the fallback)."""
    import socket
    if getattr(socket.getaddrinfo, "_avos_v4", False):
        return
    real = socket.getaddrinfo

    def getaddrinfo(*a, **k):  # type: ignore[no-untyped-def]
        res = real(*a, **k)
        return sorted(res, key=lambda r: 0 if r[0] == socket.AF_INET else 1)

    getaddrinfo._avos_v4 = True  # type: ignore[attr-defined]
    socket.getaddrinfo = getaddrinfo


_prefer_ipv4()
