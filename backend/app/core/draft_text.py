"""Clean-up shared by the agent, which writes drafts, and the send path, which sends them."""

import re

_SUBJECT_LINE = re.compile(r"^\s*subject\s*:.*(?:\r?\n)+", re.IGNORECASE)


def strip_subject_line(body: str) -> str:
    """Drop a leading "Subject: ..." the generator wrote into the draft.

    The subject is a header, so in the body it shows twice: once where it belongs and once as the
    first line of the reply.
    """
    return _SUBJECT_LINE.sub("", body, count=1).lstrip()
