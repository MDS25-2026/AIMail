"""Draws the Chrome extension's toolbar icons (16, 48, 128 px) with no image library.

A rounded square in the brand colour with a white envelope. Run after changing the brand colour:
    python3 scripts/make-extension-icons.py
"""

import struct
import zlib
from pathlib import Path

BRAND = (0x1E, 0x3A, 0x6E)  # scripts/palette.json light.brand
WHITE = (0xFF, 0xFF, 0xFF)
OUT = Path(__file__).resolve().parent.parent / "extension-public" / "icons"
SIZES = (16, 48, 128)
SUPERSAMPLE = 4


def _inside_rounded_square(x: float, y: float, radius: float) -> bool:
    cx = min(max(x, radius), 1 - radius)
    cy = min(max(y, radius), 1 - radius)
    return (x - cx) ** 2 + (y - cy) ** 2 <= radius**2


def _on_envelope(x: float, y: float, stroke: float) -> bool:
    left, right, top, bottom = 0.22, 0.78, 0.32, 0.70
    if not (left - stroke <= x <= right + stroke and top - stroke <= y <= bottom + stroke):
        return False
    on_edge = min(abs(x - left), abs(x - right), abs(y - top), abs(y - bottom)) <= stroke
    # The flap: two lines from the top corners meeting at the middle.
    mid_x, flap_y = 0.5, 0.53
    t = (x - left) / (mid_x - left) if x <= mid_x else (right - x) / (right - mid_x)
    on_flap = 0 <= t <= 1 and abs(y - (top + t * (flap_y - top))) <= stroke * 1.2
    return on_edge or on_flap


def _pixel(px: int, py: int, size: int) -> tuple[int, int, int, int]:
    stroke = max(0.045, 1.2 / size)
    hits_shape = hits_mark = 0
    for sy in range(SUPERSAMPLE):
        for sx in range(SUPERSAMPLE):
            x = (px + (sx + 0.5) / SUPERSAMPLE) / size
            y = (py + (sy + 0.5) / SUPERSAMPLE) / size
            if _inside_rounded_square(x, y, 0.22):
                hits_shape += 1
                hits_mark += _on_envelope(x, y, stroke)
    samples = SUPERSAMPLE**2
    if hits_shape == 0:
        return (0, 0, 0, 0)
    blend = hits_mark / hits_shape
    color = tuple(round(b + (w - b) * blend) for b, w in zip(BRAND, WHITE, strict=True))
    return (*color, round(255 * hits_shape / samples))


def _png(size: int) -> bytes:
    rows = b"".join(
        b"\x00" + b"".join(bytes(_pixel(x, y, size)) for x in range(size)) for y in range(size)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b"")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        (OUT / f"icon-{size}.png").write_bytes(_png(size))
        print(f"wrote icons/icon-{size}.png")
