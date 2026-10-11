"""Why a draft needs a person, as codes the dashboard words (specs/features/plain-wording-and-polish.md).

Drafts made since the agent emitted codes store them; older ones only have the agent's text, which is
read here, and only here, by its opening words.
"""

from app.agent_contract import ReviewCode, ReviewReason

# Most specific first: "does not address everything" before "does not address:".
_OPENINGS: tuple[tuple[str, ReviewCode], ...] = (
    ("possible phishing", ReviewCode.PHISHING_LINK),
    ("no policy context", ReviewCode.NOT_GROUNDED),
    ("pii: PRESIDIO_UNAVAILABLE", ReviewCode.PII_SCAN_UNAVAILABLE),
    ("pii:", ReviewCode.PII_FOUND),
    ("figures not in source:", ReviewCode.FIGURES_NOT_IN_SOURCE),
    ("critic unavailable", ReviewCode.CRITIC_UNAVAILABLE),
    ("grounding check failed", ReviewCode.GROUNDING_FAILED),
    ("does not address everything", ReviewCode.INCOMPLETE),
    ("does not address:", ReviewCode.DOES_NOT_ADDRESS),
    ("needed ", ReviewCode.REFINE_ROUNDS),
    ("repair stopped", ReviewCode.REPAIR_STOPPED),
    ("confidence ", ReviewCode.LOW_CONFIDENCE),
    ("no reply drafted", ReviewCode.NO_REPLY),
    ("no draft:", ReviewCode.NO_DRAFT),
)
# The codes whose text lists its items after the colon, and how they are separated.
_ITEM_SEPARATORS = {ReviewCode.PII_FOUND: ", ", ReviewCode.FIGURES_NOT_IN_SOURCE: ", ",
                    ReviewCode.DOES_NOT_ADDRESS: "; "}


def _from_text(text: str) -> ReviewReason:
    code = next((code for opening, code in _OPENINGS if text.startswith(opening)), ReviewCode.UNKNOWN)
    separator = _ITEM_SEPARATORS.get(code)
    items = text.split(": ", 1)[1].split(separator) if separator and ": " in text else []
    return ReviewReason(code=code, items=items)


def review_reasons(critic_checks: dict | None) -> list[ReviewReason]:
    """The stored codes, or for an older draft, its reasons read from their text."""
    checks = critic_checks or {}
    if "review_codes" in checks:
        return [ReviewReason(**reason) for reason in checks["review_codes"]]
    return [_from_text(text) for text in checks.get("review_reasons") or []]
