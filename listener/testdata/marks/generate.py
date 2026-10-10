"""Regenerates the synthetic scans for marks_live_test.go. Every name and figure is made up.

Run from this folder: python3 generate.py
"""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SIZE = (827, 1169)  # A4 at 100 dpi
HERE = Path(__file__).parent
INK = (25, 30, 110)

INVOICE = ["INVOICE No. 4471", "Bill to: Contoh Trading Sdn Bhd", "Item: Office chairs x 12",
           "Amount due: RM 1,250.00", "Due: 30 October 2026", "Thank you for your business."]
LETTER = ["Dear Sir/Madam,", "We confirm receipt of your purchase order.", "Delivery is scheduled",
          "for the week of 12 October 2026.", "Kind regards,", "Operations Team"]
FORM = ["APPLICATION FORM", "Company: ____________________", "Registration no: ____________",
        "Date: ____________", "Signature: ____________________"]


def page(lines: list[str]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 22)
    for row, line in enumerate(lines):
        draw.text((80, 100 + 48 * row), line, fill="black", font=font)
    return image, draw


def table(draw: ImageDraw.ImageDraw) -> None:
    font = ImageFont.truetype(FONT, 18)
    for row in range(6):
        y = 480 + row * 40
        draw.rectangle((80, y, 740, y + 40), outline="black")
        draw.text((90, y + 10), f"Line {row + 1}    Widget {chr(65 + row)}    RM {120 + row * 35}.00",
                  fill="black", font=font)


def logo(draw: ImageDraw.ImageDraw) -> None:
    draw.rectangle((600, 60, 760, 120), fill=(20, 90, 160))
    draw.text((615, 78), "CONTOH", fill="white", font=ImageFont.truetype(BOLD, 24))


def signature(draw: ImageDraw.ImageDraw, x: int, y: int, seed: int) -> None:
    rng = random.Random(seed)
    a, b, c = rng.uniform(4, 8), rng.uniform(1.8, 3.2), rng.uniform(15, 30)
    points = [(x + t * 2.2, y + c * math.sin(t / a) + 9 * math.sin(t / b) - 0.15 * t) for t in range(110)]
    draw.line(points, fill=INK, width=3, joint="curve")
    draw.line([(x + 20, y + 30), (x + 230, y + 22)], fill=INK, width=2)


def initials(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    draw.line([(x, y + 40), (x + 15, y), (x + 30, y + 40), (x + 45, y + 5)], fill=INK, width=3)
    draw.arc((x + 50, y, x + 90, y + 40), 30, 330, fill=INK, width=3)


def round_stamp(draw: ImageDraw.ImageDraw, x: int, y: int, colour: tuple[int, int, int]) -> None:
    draw.ellipse((x, y, x + 170, y + 170), outline=colour, width=6)
    draw.ellipse((x + 22, y + 22, x + 148, y + 148), outline=colour, width=2)
    font = ImageFont.truetype(BOLD, 18)
    draw.text((x + 38, y + 62), "CONTOH", fill=colour, font=font)
    draw.text((x + 40, y + 88), "SDN BHD", fill=colour, font=font)


def box_stamp(draw: ImageDraw.ImageDraw, x: int, y: int, word: str) -> None:
    red = (190, 30, 40)
    draw.rectangle((x, y, x + 240, y + 90), outline=red, width=6)
    draw.text((x + 30, y + 18), word, fill=red, font=ImageFont.truetype(BOLD, 44))


def face(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    skin, dark = (224, 186, 150), (60, 40, 30)
    draw.rectangle((x - 20, y - 20, x + 200, y + 260), fill=(200, 210, 225))
    draw.ellipse((x + 10, y + 120, x + 170, y + 300), fill=(70, 80, 120))
    draw.ellipse((x + 35, y + 10, x + 145, y + 150), fill=skin)
    draw.chord((x + 30, y, x + 150, y + 90), 180, 360, fill=dark)
    for eye in (x + 62, x + 103):
        draw.ellipse((eye, y + 65, eye + 14, y + 75), fill="white")
        draw.ellipse((eye + 4, y + 66, eye + 10, y + 74), fill=dark)
    draw.line([(x + 90, y + 80), (x + 85, y + 105), (x + 93, y + 107)], fill=(150, 100, 80), width=2)
    draw.arc((x + 70, y + 105, x + 112, y + 128), 20, 160, fill=(150, 60, 60), width=3)


def save(image: Image.Image, folder: str, name: str) -> None:
    out = HERE / folder
    out.mkdir(exist_ok=True)
    image.save(out / f"{name}.png", optimize=True)


def clear_pages() -> None:
    for name, lines, extra in [
        ("invoice", INVOICE, None), ("letter", LETTER, None), ("blank-form", FORM, None),
        ("invoice-table", INVOICE, table), ("invoice-logo", INVOICE, logo),
        ("letter-logo", LETTER, logo), ("table-only", ["PRICE LIST 2026"], table),
        ("form-table", FORM, table),
    ]:
        image, draw = page(lines)
        if extra:
            extra(draw)
        save(image, "clear", name)


def marked_pages() -> None:
    cases = [
        ("signed-letter", LETTER, lambda d: signature(d, 90, 420, 1)),
        ("signed-invoice", INVOICE, lambda d: signature(d, 120, 520, 2)),
        ("signed-form", FORM, lambda d: signature(d, 230, 270, 3)),
        ("signed-logo", INVOICE, lambda d: (logo(d), signature(d, 100, 560, 4))),
        ("initials", LETTER, lambda d: initials(d, 100, 430)),
        ("round-stamp", INVOICE, lambda d: round_stamp(d, 520, 450, (30, 60, 170))),
        ("red-seal", LETTER, lambda d: round_stamp(d, 480, 420, (190, 30, 40))),
        ("paid-stamp", INVOICE, lambda d: box_stamp(d, 420, 500, "PAID")),
        ("received-stamp", LETTER, lambda d: box_stamp(d, 400, 450, "DITERIMA")),
        ("photo-form", FORM, lambda d: face(d, 560, 300)),
        ("photo-letter", LETTER, lambda d: face(d, 540, 420)),
        ("signed-and-stamped", INVOICE, lambda d: (signature(d, 100, 560, 5), round_stamp(d, 450, 520, (30, 60, 170)))),
    ]
    for name, lines, mark in cases:
        image, draw = page(lines)
        mark(draw)
        save(image, "marked", name)


if __name__ == "__main__":
    clear_pages()
    marked_pages()
