"""Deterministic near-black 1600x900 CleanYourTV wallpaper.

Uses only Python standard library on Termux. The official Android BitmapFactory
reads image content by signature, so the generated PNG is permitted at the
launcher-owned 'wallpaper.jpg' ThemeProvider path. It never modifies Android
system wallpapers, settings or stock launcher.
"""
from __future__ import annotations

import math
import struct
import zlib

WIDTH, HEIGHT = 1600, 900


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def generate() -> bytes:
    rgb = bytearray(WIDTH * HEIGHT * 3)

    def arc(x0: int, x1: int, curve, strength: float, halo: float) -> None:
        for x in range(x0, x1):
            t = (x - x0) / max(1, x1 - x0 - 1)
            center_y = curve(t)
            intensity = strength * (math.sin(math.pi * t) ** 0.65)
            ymin = max(0, int(center_y - 3.2 * halo))
            ymax = min(HEIGHT - 1, int(center_y + 3.2 * halo))
            for y in range(ymin, ymax + 1):
                dy = y - center_y
                bloom = intensity * math.exp(-0.5 * (dy / halo) ** 2)
                line = intensity * 0.47 * math.exp(-0.5 * (dy / 1.5) ** 2)
                value = int(bloom + line)
                i = (y * WIDTH + x) * 3
                rgb[i] = min(105, rgb[i] + value)
                rgb[i + 1] = min(13, rgb[i + 1] + value // 11)
                rgb[i + 2] = min(11, rgb[i + 2] + value // 14)

    # The two faint arcs from the approved minimal OLED concept.
    arc(560, 1550, lambda t: 380 - 366 * (t ** 1.52) + 16 * math.sin(math.pi * t), 45, 24)
    arc(40, 770, lambda t: 840 - 180 * (t ** 1.4), 13, 32)

    stride = WIDTH * 3
    rows = (b"\x00" + rgb[y * stride:(y + 1) * stride] for y in range(HEIGHT))
    ihdr = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", ihdr)
        + png_chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + png_chunk(b"IEND", b"")
    )


if __name__ == "__main__":
    from pathlib import Path
    path = Path(__file__).resolve().parent.parent / "presets/cleanyourtv-boxy/wallpaper-preview.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(generate())
    print("PREVIEW_OK: " + str(path))
