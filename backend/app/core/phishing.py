"""The phishing signal on a masked email body, shared by the agent's review and holding replies.

A request for credentials or payment details beside a link is the shape of phishing. Checked on the
masked body: masking removes names and addresses, never URLs or these words. Deterministic on
purpose, so an email cannot talk its way past it.
"""

import re

_CREDENTIAL_ASK = re.compile(
    r"\b(?:password|passcode|log ?in|sign ?in|verify your (?:account|identity)|one[- ]time"
    r" (?:password|code)|otp|pin|security code|bank details|card details|credentials)\b",
    re.IGNORECASE,
)
# A scheme, "www.", or a bare domain followed by a path ("secure-bank.com/verify").
_LINK = re.compile(r"\bhttps?://|\bwww\.|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}/", re.IGNORECASE)


def phishing_signal(email_body: str) -> bool:
    return bool(_CREDENTIAL_ASK.search(email_body) and _LINK.search(email_body))
