"""Verify the dashboard palette: WCAG 2.1 contrast in both themes, and colour-blind separation.

Run: python3 scripts/check-palette.py           (exit 1 on any failure or a stale src/palette.css)
     python3 scripts/check-palette.py --quiet   (print failures only; what make check uses)
     python3 scripts/check-palette.py --write   (regenerate src/palette.css from palette.json)

Contrast follows WCAG 2.1 SC 1.4.3 (4.5:1 text) and 1.4.11 (3:1 non-text). Colour-blind vision is
simulated with the Machado, Oliveira & Fernandes (2009) matrices at full severity, and status
colours must stay at least MIN_DELTA_E apart (CIE76 in Lab) under each deficiency.
"""

import itertools
import json
import math
import sys
from pathlib import Path

TEXT_CONTRAST = 4.5
NON_TEXT_CONTRAST = 3.0
MIN_DELTA_E = 20.0

MACHADO = {
    "protanopia": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
                   [-0.003882, -0.048116, 1.051998]],
    "deuteranopia": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
                     [-0.011820, 0.042940, 0.968881]],
    "tritanopia": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
                   [0.004733, 0.691367, 0.303900]],
}


def rgb(hex_colour: str) -> list[float]:
    return [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    r, g, b = (linear(c) for c in rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def lab(linear_rgb: list[float]) -> tuple[float, float, float]:
    r, g, b = linear_rgb
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def simulate(hex_colour: str, matrix: list[list[float]]) -> list[float]:
    lin = [linear(c) for c in rgb(hex_colour)]
    return [min(1.0, max(0.0, sum(m * c for m, c in zip(row, lin)))) for row in matrix]


def delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


CSS_PATH = Path(__file__).parent.parent / "src" / "palette.css"
CSS_HEADER = "/* Generated from scripts/palette.json by scripts/check-palette.py --write. Do not edit. */\n"


def oklch(hex_colour: str) -> str:
    """sRGB hex to CSS oklch(), via Ottosson's OKLab."""
    r, g, b = (linear(c) for c in rgb(hex_colour))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    chroma = (a * a + b2 * b2) ** 0.5
    hue = (math.degrees(math.atan2(b2, a)) + 360) % 360 if chroma > 1e-4 else 0
    return f"oklch({lightness:.4f} {chroma:.4f} {hue:.2f})"


def css(spec: dict) -> str:
    blocks = []
    for selector, theme in ((":root", "light"), (".dark", "dark")):
        lines = [f"  --{name}: {oklch(value)};" for name, value in spec[theme].items()]
        scheme = "light" if theme == "light" else "dark"
        blocks.append(f"{selector} {{\n  color-scheme: {scheme};\n" + "\n".join(lines) + "\n}\n")
    return CSS_HEADER + "\n".join(blocks)


def main() -> int:
    spec = json.loads((Path(__file__).parent / "palette.json").read_text())
    if "--write" in sys.argv:
        CSS_PATH.write_text(css(spec))
        print(f"wrote {CSS_PATH.name}")
    failures = []
    if not CSS_PATH.exists() or CSS_PATH.read_text() != css(spec):
        failures.append("src/palette.css is stale: run with --write")
    for theme in ("light", "dark"):
        colours = spec[theme]
        for pairs, minimum in ((spec["text_pairs"], TEXT_CONTRAST),
                               (spec["non_text_pairs"], NON_TEXT_CONTRAST)):
            for fg, bg in pairs:
                ratio = contrast(colours[fg], colours[bg])
                status = "ok " if ratio >= minimum else "FAIL"
                if ratio < minimum or "--quiet" not in sys.argv:
                    print(f"{status} {theme:5} {fg:>13} on {bg:<14} {ratio:5.2f}:1 (min {minimum})")
                if ratio < minimum:
                    failures.append(f"{theme} {fg}/{bg}")
        for vision, matrix in [("normal", None), *MACHADO.items()]:
            for a, b in itertools.combinations(spec["must_differ"], 2):
                la = lab(simulate(colours[a], matrix) if matrix else [linear(c) for c in rgb(colours[a])])
                lb = lab(simulate(colours[b], matrix) if matrix else [linear(c) for c in rgb(colours[b])])
                distance = delta_e(la, lb)
                if distance < MIN_DELTA_E:
                    failures.append(f"{theme} {vision} {a}~{b} dE={distance:.1f}")
                    print(f"FAIL {theme:5} {vision:12} {a} vs {b}: dE {distance:.1f}")
    if failures:
        print(f"\n{len(failures)} failure(s): " + "; ".join(failures))
    elif "--quiet" not in sys.argv:
        print("\nall checks pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
