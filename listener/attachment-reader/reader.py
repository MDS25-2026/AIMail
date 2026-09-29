"""Local attachment reader: text out of documents, PII out of images, before anything else reads.

Runs beside the listener on 127.0.0.1 and never calls out. For each attachment:
- a PDF page with a text layer, a .docx or an .xlsx gives back plain text, which the listener
  masks like any body text, so it needs no vision model at all;
- a scanned page or an image is redacted here, and returned only if the local OCR read its text
  confidently. Text the local OCR cannot read cannot be checked for PII, so that page is skipped
  rather than handed to a stronger remote reader that would see what was never masked.
"""

from __future__ import annotations

import base64
import html
import io
import logging
import os
import re
import zipfile
from dataclasses import dataclass, field

import pypdfium2 as pdfium
import pytesseract
from flask import Flask, jsonify, request
from PIL import Image, ImageDraw
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult

logger = logging.getLogger("attachment-reader")

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
IMAGE_PREFIX = "image/"

MAX_REQUEST_BYTES = 10_000_000
MAX_PDF_PAGES = 20
# Per zip member, declared and actual: a 1 KB docx can inflate to gigabytes.
MAX_MEMBER_BYTES = 8_000_000
MAX_ZIP_MEMBERS = 500
# Fewer characters than this on a PDF page means a scan, or a page that is only a picture.
MIN_TEXT_LAYER_CHARS = 20
RENDER_SCALE = 2.0  # ~144 dpi: Tesseract's accuracy drops sharply below ~100 dpi.

# The privacy gate. Tesseract's per-word confidence is 0-100.
LOW_CONFIDENCE = 60
MAX_LOW_CONFIDENCE_SHARE = 0.2

REDACTION_FILL = (0, 0, 0)
SCORE_THRESHOLD = 0.4
# The listener's text entities plus the ones its regex floor catches in text. DATE_TIME is
# deliberately absent: "Payment due 30 September 2026" is business content, not personal data,
# and the REST redactor's defaults were blacking it out (docs/known-issues.md).
IMAGE_ENTITIES = [
    "PERSON", "LOCATION", "ORGANIZATION", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD",
    "IBAN_CODE", "ACCOUNT_NUMBER", "MY_NRIC", "MY_PHONE", "SWIFT_CODE",
]


# Identifiers with a fixed shape: OCR noise around a redaction box cannot fake one of these.
FORMAT_ENTITIES = [
    "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "MY_NRIC", "MY_PHONE", "SWIFT_CODE",
]
MAX_REDACTION_PASSES = 3


def _recognizer(entity: str, regex: str, score: float, context: list[str]) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=entity, patterns=[Pattern(entity.lower(), regex, score)], context=context
    )


# Mirrors listener/main.go and backend/email_agent.py, where the same formats are recognised.
AD_HOC_RECOGNIZERS = [
    _recognizer("MY_NRIC", r"\b\d{6}[- ]?\d{2}[- ]?\d{4}\b", 0.6, ["ic", "nric", "mykad"]),
    _recognizer("MY_PHONE", r"\b(?:\+?60|0)1\d[- ]?\d{3,4}[- ]?\d{4}\b", 0.6, ["phone", "tel"]),
    _recognizer("ACCOUNT_NUMBER", r"\b\d{4,16}\b", 0.3, ["account", "acc", "bank", "ref"]),
    _recognizer("SWIFT_CODE", r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b", 0.3,
                ["swift", "bic", "bank"]),
]


class ReaderError(ValueError):
    """The attachment cannot be read. Maps to 422; the listener skips that attachment."""


@dataclass
class Reading:
    texts: list[str] = field(default_factory=list)
    images: list[bytes] = field(default_factory=list)
    skipped_pages: int = 0
    pages: int = 0

    def as_json(self) -> dict:
        return {
            "text": "\n\n".join(t for t in self.texts if t.strip()),
            "images": [{"mime_type": "image/png", "data": base64.b64encode(i).decode()}
                       for i in self.images],
            "skipped_pages": self.skipped_pages,
            "pages": self.pages,
        }


@dataclass(frozen=True)
class Word:
    text: str
    confidence: float
    box: tuple[int, int, int, int]  # left, top, right, bottom
    line: tuple[int, int, int]  # Tesseract's block, paragraph and line numbers
    start: int  # character offsets into the page text
    end: int


def join_lines(words: list[Word]) -> tuple[str, list[Word]]:
    """Words as text, one line per OCR line, each word re-anchored to its new offsets."""
    text, placed, line = "", [], None
    for word in words:
        if text:
            text += " " if word.line == line else "\n"
        line = word.line
        placed.append(Word(word.text, word.confidence, word.box, word.line,
                           len(text), len(text) + len(word.text)))
        text += word.text
    return text, placed


def ocr_words(image: Image.Image) -> tuple[str, list[Word]]:
    """The page as text with one line per OCR line, and every word with its offsets.

    Lines are kept as lines: joined into one run, NER tagged "Aisyah Rahman Email" as a single
    PERSON, and a match spanning a label cannot be mapped back onto the name's pixels.
    """
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words: list[Word] = []
    for i, raw in enumerate(data["text"]):
        token, confidence = str(raw).strip(), float(data["conf"][i])
        if not token or confidence < 0:
            continue
        left, top = data["left"][i], data["top"][i]
        box = (left, top, left + data["width"][i], top + data["height"][i])
        line = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        words.append(Word(token, confidence, box, line, 0, 0))
    return join_lines(words)


def confidently_read(words: list[Word]) -> bool:
    """True when the local OCR found words and read nearly all of them confidently."""
    if not words:
        return False
    low = sum(1 for word in words if word.confidence < LOW_CONFIDENCE)
    return low / len(words) <= MAX_LOW_CONFIDENCE_SHARE


class Redactor:
    def __init__(self, analyzer: AnalyzerEngine) -> None:
        self.analyzer = analyzer

    def _findings(self, text: str, entities: list[str]) -> list[RecognizerResult]:
        return self.analyzer.analyze(
            text=text, language="en", entities=entities, score_threshold=SCORE_THRESHOLD,
            ad_hoc_recognizers=AD_HOC_RECOGNIZERS,
        )

    def words_to_hide(self, words: list[Word], text: str) -> set[int]:
        """Every word overlapping a finding, re-analysed until nothing new turns up.

        Removing a tagged first name can leave its surname reading as a name on its own, so one
        pass is not enough. This runs on the OCR text, not on pixels, so box edges cannot
        manufacture findings.
        """
        hidden: set[int] = set()
        current_text, current = text, list(enumerate(words))
        for _ in range(MAX_REDACTION_PASSES):
            new = {index for finding in self._findings(current_text, IMAGE_ENTITIES)
                   for index, word in current
                   if word.start < finding.end and finding.start < word.end}
            if not new:
                break
            hidden |= new
            survivors = [(i, w) for i, w in enumerate(words) if i not in hidden]
            current_text, placed = join_lines([w for _, w in survivors])
            current = [(i, w) for (i, _), w in zip(survivors, placed)]
        return hidden

    def redact(self, image: Image.Image) -> bytes | None:
        """Redacted PNG, or None when this image must not leave the machine.

        Two gates. The first: the local OCR must have read the page confidently, since text it
        cannot read cannot be checked. The second: OCR of the redacted pixels must find no
        fixed-format identifier, so a box that missed its word is caught here instead of by the
        remote reader. Names are not re-checked on pixels: box edges make OCR read "Email:" as
        "Ena:", which NER then tags as a person.
        """
        rgb = image.convert("RGB")
        text, words = ocr_words(rgb)
        if not confidently_read(words):
            return None
        redacted = rgb.copy()
        draw = ImageDraw.Draw(redacted)
        for index in self.words_to_hide(words, text):
            draw.rectangle(words[index].box, fill=REDACTION_FILL)
        if self._findings(ocr_words(redacted)[0], FORMAT_ENTITIES):
            logger.warning("redaction left a detectable identifier; image withheld")
            return None
        buffer = io.BytesIO()
        redacted.save(buffer, format="PNG")
        return buffer.getvalue()


def add_image(reading: Reading, redactor: Redactor, image: Image.Image) -> None:
    reading.pages += 1
    png = redactor.redact(image)
    if png is None:
        reading.skipped_pages += 1
        return
    reading.images.append(png)


def read_pdf(data: bytes, redactor: Redactor) -> Reading:
    try:
        document = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise ReaderError(f"unreadable PDF: {error}") from error
    reading = Reading()
    for index in range(min(len(document), MAX_PDF_PAGES)):
        page = document[index]
        text = page.get_textpage().get_text_bounded()
        if len(text.strip()) >= MIN_TEXT_LAYER_CHARS:
            reading.pages += 1
            reading.texts.append(text)
            continue
        add_image(reading, redactor, page.render(scale=RENDER_SCALE).to_pil())
    return reading


def _member(archive: zipfile.ZipFile, name: str) -> str:
    info = archive.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ReaderError(f"{name} declares {info.file_size} bytes")
    with archive.open(info) as handle:
        raw = handle.read(MAX_MEMBER_BYTES + 1)
    if len(raw) > MAX_MEMBER_BYTES:
        raise ReaderError(f"{name} inflates past its cap")
    return raw.decode("utf-8", errors="replace")


def _open_zip(data: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise ReaderError("not an Office document") from error
    if len(archive.infolist()) > MAX_ZIP_MEMBERS:
        raise ReaderError("too many archive members")
    return archive


_XML_TAG = re.compile(r"<[^>]+>")
_PARAGRAPH_END = re.compile(r"</w:p>|<w:br/>|<w:tab/>")
_XLSX_TEXT = re.compile(r"<(?:t|v)(?:\s[^>]*)?>([^<]*)</(?:t|v)>")


def read_docx(data: bytes) -> Reading:
    with _open_zip(data) as archive:
        xml = _member(archive, "word/document.xml")
    text = html.unescape(_XML_TAG.sub("", _PARAGRAPH_END.sub("\n", xml)))
    return Reading(texts=[text], pages=1)


def read_xlsx(data: bytes) -> Reading:
    """Every shared string and cell value, one per line. Layout is lost; content is not."""
    with _open_zip(data) as archive:
        names = [n for n in archive.namelist()
                 if n == "xl/sharedStrings.xml" or n.startswith("xl/worksheets/sheet")]
        values = [html.unescape(v) for n in names for v in _XLSX_TEXT.findall(_member(archive, n))]
    return Reading(texts=["\n".join(v for v in values if v.strip())], pages=1)


def read_image(data: bytes, redactor: Redactor) -> Reading:
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (OSError, Image.DecompressionBombError) as error:
        raise ReaderError(f"unreadable image: {error}") from error
    reading = Reading()
    add_image(reading, redactor, image)
    return reading


def read_attachment(data: bytes, mime_type: str, redactor: Redactor) -> Reading:
    if mime_type == PDF_MIME:
        return read_pdf(data, redactor)
    if mime_type == DOCX_MIME:
        return read_docx(data)
    if mime_type == XLSX_MIME:
        return read_xlsx(data)
    if mime_type.startswith(IMAGE_PREFIX):
        return read_image(data, redactor)
    raise ReaderError(f"unsupported type {mime_type}")


def create_app(analyzer: AnalyzerEngine | None = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
    redactor = Redactor(analyzer or AnalyzerEngine())

    @app.get("/health")
    def health() -> tuple[str, int]:
        return "ok", 200

    @app.post("/read")
    def read() -> tuple[object, int]:
        upload = request.files.get("file")
        mime_type = request.form.get("mime_type", "")
        if upload is None:
            return jsonify(error="missing file"), 400
        try:
            reading = read_attachment(upload.read(), mime_type, redactor)
        except ReaderError as error:
            # The reason only: never the file name or any content, which may carry PII.
            logger.warning("attachment unreadable: %s", error)
            return jsonify(error=str(error)), 422
        return jsonify(reading.as_json()), 200

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.environ.get("PORT", "3000")))
