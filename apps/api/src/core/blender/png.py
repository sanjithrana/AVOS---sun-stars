"""Minimal dependency-free PNG encoder (grayscale / RGB, 8-bit)."""

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode_png(width: int, height: int, rows: list[bytes], *, channels: int, text: dict[str, str] | None = None) -> bytes:
    """rows: one bytes object per scanline, width*channels long."""
    color_type = {1: 0, 3: 2}[channels]
    raw = b"".join(b"\x00" + row for row in rows)  # filter type 0 per row
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    for key, value in (text or {}).items():
        png += _chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("latin-1", "replace"))
    png += _chunk(b"IDAT", zlib.compress(raw, 9))
    png += _chunk(b"IEND", b"")
    return png


def png_size(data: bytes) -> tuple[int, int]:
    """(width, height) from a PNG's IHDR."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", data[16:24])
