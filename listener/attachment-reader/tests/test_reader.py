"""Attachment reader, against the real Tesseract and spaCy models in the image.

Run with: make test-reader
"""

import base64
import io
import zipfile

import pytesseract
import pytest
from PIL import Image, ImageDraw, ImageFont

import reader

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


@pytest.fixture(scope="module")
def client():
    return reader.create_app().test_client()


def _image(lines: list[str]) -> Image.Image:
    image = Image.new("RGB", (1400, 110 * len(lines) + 60), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, 44)
    for row, line in enumerate(lines):
        draw.text((40, 40 + 110 * row), line, fill="black", font=font)
    return image


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _read(client, data: bytes, mime_type: str):
    return client.post("/read", data={"file": (io.BytesIO(data), "a"), "mime_type": mime_type},
                       content_type="multipart/form-data")


def _ocr(png_b64: str) -> str:
    return pytesseract.image_to_string(Image.open(io.BytesIO(base64.b64decode(png_b64))))


INVOICE = [
    "Invoice for Aisyah Rahman",
    "Email: aisyah.rahman@example.com",
    "Payment due 30 September 2026",
    "Total: RM 1,250.00",
]


def test_an_image_comes_back_redacted_with_business_content_intact(client):
    body = _read(client, _png(_image(INVOICE)), "image/png").get_json()
    assert len(body["images"]) == 1
    text = _ocr(body["images"][0]["data"])
    assert "example.com" not in text and "Aisyah" not in text
    assert "September" in text, "dates are business content and must survive (known-issues.md)"
    assert "1,250.00" in text


def test_a_scanned_pdf_page_is_rasterised_and_redacted(client):
    buffer = io.BytesIO()
    _image(INVOICE).save(buffer, format="PDF")
    body = _read(client, buffer.getvalue(), reader.PDF_MIME).get_json()
    assert body["pages"] == 1 and len(body["images"]) == 1 and body["text"] == ""
    assert "example.com" not in _ocr(body["images"][0]["data"])


def test_an_image_the_local_ocr_cannot_read_never_leaves(client):
    noise = Image.effect_noise((800, 400), 120).convert("RGB")
    body = _read(client, _png(noise), "image/png").get_json()
    assert body["images"] == [] and body["skipped_pages"] == 1


def _text_pdf(text: str) -> bytes:
    """A one-page PDF with a real text layer, built by hand so no PDF writer is needed."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
         b"/Resources << /Font << /F1 5 0 R >> >> >>"),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for number, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    out.write(b"".join(b"%010d 00000 n \n" % o for o in offsets))
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objects) + 1, xref))
    return out.getvalue()


def test_a_text_pdf_gives_text_and_no_image(client):
    body = _read(client, _text_pdf("Quarterly report: revenue grew 12 percent"),
                 reader.PDF_MIME).get_json()
    assert "revenue grew 12 percent" in body["text"]
    assert body["images"] == []


def _office(members: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_docx_paragraphs_become_lines_and_entities_decode(client):
    xml = "<w:p><w:r><w:t>Terms &amp; conditions</w:t></w:r></w:p><w:p><w:t>Line two</w:t></w:p>"
    body = _read(client, _office({"word/document.xml": xml}), reader.DOCX_MIME).get_json()
    assert body["text"].split("\n")[:2] == ["Terms & conditions", "Line two"]


def test_xlsx_shared_strings_and_values_are_read(client):
    shared = "<sst><si><t>Widget</t></si></sst>"
    sheet = "<sheetData><row><c t='s'><v>0</v></c><c><v>42</v></c></row></sheetData>"
    data = _office({"xl/sharedStrings.xml": shared, "xl/worksheets/sheet1.xml": sheet})
    text = _read(client, data, reader.XLSX_MIME).get_json()["text"]
    assert "Widget" in text and "42" in text


def test_a_zip_bomb_member_is_refused(client, monkeypatch):
    monkeypatch.setattr(reader, "MAX_MEMBER_BYTES", 1000)
    data = _office({"word/document.xml": "<w:t>" + "a" * 5000 + "</w:t>"})
    assert _read(client, data, reader.DOCX_MIME).status_code == 422


@pytest.mark.parametrize("data, mime_type", [
    (b"not a pdf", reader.PDF_MIME),
    (b"not a zip", reader.DOCX_MIME),
    (b"not an image", "image/png"),
    (b"anything", "application/x-msdownload"),
])
def test_unreadable_or_unsupported_input_is_a_422(client, data, mime_type):
    assert _read(client, data, mime_type).status_code == 422


def _words(confidences: list[float]) -> list[reader.Word]:
    return [reader.Word("w", c, (0, 0, 1, 1), (1, 1, 1), 0, 1) for c in confidences]


@pytest.mark.parametrize("confidences, expected", [
    ([95, 91, 88], True),
    ([95, 30, 20, 90, 91], False),
    ([], False),
])
def test_the_gate_passes_only_confident_reads(confidences, expected):
    assert reader.confidently_read(_words(confidences)) is expected


def test_ocr_keeps_lines_apart_so_a_name_does_not_swallow_the_next_label():
    text, words = reader.ocr_words(_image(["Invoice for Aisyah Rahman", "Email: x"]))
    assert "Rahman\nEmail" in text
    assert all(text[w.start:w.end] == w.text for w in words)


@pytest.fixture(scope="module")
def redactor():
    from presidio_analyzer import AnalyzerEngine

    return reader.Redactor(AnalyzerEngine())


def test_a_redaction_that_misses_an_identifier_is_withheld_not_sent(redactor, monkeypatch):
    monkeypatch.setattr(redactor, "words_to_hide", lambda words, text: set())
    assert redactor.redact(_image(INVOICE)) is None


def test_a_full_invoice_with_labels_beside_boxes_is_still_sent(redactor):
    """Box edges turn "Email:" into "Ena:"; that artefact must not withhold a clean redaction."""
    lines = ["INVOICE INV-2026-0914", "Bill to: Aisyah Rahman",
             "Email: aisyah.rahman@example.com", "Phone: 012-345 6789",
             "Payment due 30 September 2026", "Total: RM 1,250.00"]
    png = redactor.redact(_image(lines))
    assert png is not None
    text = pytesseract.image_to_string(Image.open(io.BytesIO(png)))
    assert "Aisyah" not in text and "example.com" not in text and "6789" not in text
    assert "September" in text and "1,250.00" in text


def test_hiding_repeats_until_nothing_new_reads_as_pii(redactor):
    text, words = reader.ocr_words(_image(["Signed by Aisyah Rahman binti Abdullah"]))
    hidden = {words[i].text for i in redactor.words_to_hide(words, text)}
    assert {"Aisyah", "Rahman"} <= hidden


def test_a_docx_without_its_main_part_is_a_422(client):
    assert _read(client, _office({"word/other.xml": "<x/>"}), reader.DOCX_MIME).status_code == 422


def test_a_workbook_whose_sheets_inflate_past_the_total_cap_is_refused(client, monkeypatch):
    monkeypatch.setattr(reader, "MAX_TOTAL_INFLATED_BYTES", 5000)
    sheets = {f"xl/worksheets/sheet{i}.xml": "<v>1</v>" + "x" * 2000 for i in range(4)}
    assert _read(client, _office(sheets), reader.XLSX_MIME).status_code == 422


def test_a_huge_page_is_rendered_at_a_bounded_size():
    # A 5 m square poster page: the full scale would be about 800 Mpx.
    scale = reader.render_scale(14_000, 14_000)
    assert (14_000 * scale) * (14_000 * scale) <= reader.MAX_RENDER_PIXELS * 1.001


def test_pages_past_the_cap_are_reported_not_silently_dropped(client, monkeypatch):
    monkeypatch.setattr(reader, "MAX_PDF_PAGES", 0)
    body = _read(client, _text_pdf("Quarterly report"), reader.PDF_MIME).get_json()
    assert body["unread_pages"] == 1 and body["pages"] == 0
