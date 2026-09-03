"""How an approved draft is turned into a sendable message.

Sent as text/plain only, the body is folded at 78 characters to satisfy RFC 2045 and clients
render that width literally — a narrow ragged column regardless of window size. An HTML
alternative lets the reader's client choose the measure instead.
"""

import base64

from app.gmail_send import _build_raw

BODY = (
    "Subject: Re: Invoice INV-2026-0914 - License Count\n\n"
    "Hi there,\n\n"
    "Thank you for following up. We reviewed the invoice and agree the count was wrong.\n\n"
    "Regards,\nAImail\nOperations"
)


def _decoded(body: str = BODY, subject: str = "Invoice INV-2026-0914") -> str:
    return base64.urlsafe_b64decode(_build_raw("someone@example.com", subject, body)).decode()


def test_the_generators_subject_line_is_not_repeated_in_the_body():
    raw = _decoded()
    # Once as the header, never as the first visible line of the reply.
    assert raw.count("Subject: Re: Invoice INV-2026-0914") == 1
    assert "License Count" not in raw


def test_both_an_html_and_a_plain_text_part_are_sent():
    raw = _decoded()
    assert "multipart/alternative" in raw
    assert 'Content-Type: text/plain; charset="utf-8"' in raw
    assert 'Content-Type: text/html; charset="utf-8"' in raw


def test_paragraphs_become_paragraphs_so_the_client_reflows_them():
    raw = _decoded()
    assert "<p>Hi there,</p>" in raw
    # A signature's deliberate breaks survive as <br>, unlike wrapping inside a paragraph.
    assert "Regards,<br>AImail<br>Operations" in raw


def test_an_existing_re_prefix_is_not_doubled():
    assert "Subject: Re: Re:" not in _decoded(subject="Re: Invoice INV-2026-0914")


def test_html_special_characters_cannot_break_out_of_the_markup():
    raw = _decoded(body="Hi,\n\nTerms & conditions <b>apply</b> for the refund.")
    # Scoped to the HTML part: the plain-text alternative legitimately carries the raw characters.
    html_part = raw[raw.index("text/html") :]
    assert "&amp;" in html_part and "&lt;b&gt;" in html_part
    assert "<b>apply</b>" not in html_part


def test_a_draft_without_a_subject_line_is_left_alone():
    raw = _decoded(body="Hi there,\n\nNo subject line in this one.")
    assert "<p>Hi there,</p>" in raw
    assert "No subject line in this one." in raw
