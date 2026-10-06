# Attachment reading: local first, masked before any model

- **Status:** shipped
- **Owner:** veyroxie (Lane A code, pending JiaJun's review)
- **Related issue:** #82, epic #12; hackathon-reuse review (vision)
- **Last updated:** 2026-09-29

## Goal

Read what attachments say (images, scanned and text PDFs, .docx, .xlsx) without any
unredacted attachment content leaving the machine.

## Scope

**In scope**
- `listener/attachment-reader`: a local container (Flask, on the pinned presidio-image-redactor
  image for Tesseract 5 and spaCy `en_core_web_lg`, plus `pypdfium2`) with `POST /read`.
- Text PDF pages, .docx and .xlsx come back as text; the listener masks it like body text.
- Images and scanned pages are redacted locally and released only past three gates (below).
- The listener sends only released images to Gemini, and masks the transcript again.
- Dates are no longer redacted in attachments (`DATE_TIME` is not in the entity list).

**Out of scope**
- Faces, signatures and handwriting: nothing here detects them. Identity documents, where they
  matter most, are withheld whole (gate 2); on any other image they are not.
- Legacy .doc/.xls, archives, and anything not listed above: skipped.

## The three gates

1. **Confidence.** Tesseract must have found words, and at most 20% of them below 60 confidence.
   Text the local OCR cannot read cannot be checked for PII, so the page is withheld rather than
   handed to a stronger remote reader.
2. **Identity documents.** If the OCR text holds an IC number or a passport number or
   machine-readable line, the image is withheld whole (2026-10-04): its face, signature and MRZ
   cannot be boxed out word by word.
3. **Verification.** Names and places are found by NER over the OCR text, re-run until removing
   the found words turns up nothing new. Then the redacted pixels are OCR'd again, and any
   fixed-format identifier still detectable (email, phone, IC, card, IBAN) withholds the
   page. Names are not re-checked on pixels: box edges make OCR read "Email:" as "Ena:", which
   NER tags as a person.

## Acceptance criteria (`make test-reader`, `go test ./...` in listener/)

- [x] Given a synthetic invoice image, the name, email and phone are unreadable in the result and
      the due date and total are readable.
- [x] Given a scanned PDF, the page is rasterised, redacted and returned as an image.
- [x] Given a text PDF, text comes back and no image does.
- [x] Given noise or a blank page, nothing is released and the page counts as skipped.
- [x] Given a redaction that missed an identifier, the page is withheld.
- [x] Given a MyKad image or a passport page, the whole image is withheld.
- [x] Given a zip member inflating past 8 MB, or an unreadable or unsupported file, the reply is 422.
- [x] Given an unreachable reader, the listener skips the attachment and never OCRs it.

## API surface

`POST /read` (multipart: `file`, `mime_type`) returns
`{"text": str, "images": [{"mime_type": "image/png", "data": base64}], "skipped_pages": int,
"pages": int}`, or 422 `{"error": reason}`. Local only; the file name is never sent.

## Security & privacy notes

The reader binds to 127.0.0.1 and makes no outbound calls. Its logs carry reasons only, never
file names or content. The audit row per attachment records type, page counts, images sent and
pages withheld.

## Decisions

- 2026-09-29: own the OCR-to-box mapping instead of using `ImageRedactorEngine`. Rationale: it
  analysed the page as one run of text, so NER tagged "Aisyah Rahman Email" as a single PERSON and
  the mapping missed the name entirely (caught by the tests). Alternatives: the REST redactor, which
  also applied DATE_TIME.
- 2026-09-29: build on the pinned presidio-image-redactor image. Rationale: it already carries the
  OCR and NER models, all MIT/Apache. Alternatives: a fresh image, which is a second 2 GB model
  stack to maintain. `pypdfium2` (Apache-2.0/BSD) over PyMuPDF (AGPL).
