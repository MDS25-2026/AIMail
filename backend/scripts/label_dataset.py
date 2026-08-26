"""Label a sample of the Enron corpus with LOW/MEDIUM/HIGH importance via Gemini.

LLM-assisted labeling (document it as such — NOT hand-labeled gold data). Samples systematically
across the corpus so labels aren't all from one mailbox, parses subject+body out of the raw email,
and batches emails per Gemini call to stay under the free-tier rate limit. Output is a CSV with
`text,label` columns, ready for `make baseline DATASET=... TEXT=text LABEL=label`.

Usage (from backend/, needs GEMINI_API_KEY or GOOGLE_API_KEY in ../.env):
    python scripts/label_dataset.py <emails.csv | archive.zip> --limit 1500 --out labeled.csv
"""

import argparse
import csv
import json
import os
import sys
import time
import zipfile
from email import message_from_string
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
# gemini-3.5-flash is a step up from flash-lite with usable free quota (Pro is quota-locked on the
# free tier). Override with --model. The label quality mostly comes from the rubric below anyway.
_DEFAULT_MODEL = "gemini-3.5-flash"
_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

_RUBRIC = (
    "Label each email HIGH, MEDIUM, or LOW by how much it needs the recipient's attention.\n"
    "HIGH - any of:\n"
    "  - asks the recipient to reply, decide, approve, or do a task;\n"
    "  - high-stakes content: money, contracts, legal, deals, outages, escalations, urgent problems;\n"
    "  - reads like a directive or request from someone in authority.\n"
    "LOW - any of:\n"
    "  - automated or bulk: newsletters, notifications, system mail, marketing, auto-replies;\n"
    "  - purely social or logistical: thank-yous, small talk, casual banter, personal notes.\n"
    "MEDIUM - everything else: work-relevant and informative but needs no direct action from the\n"
    "  recipient (FYI, status updates, discussion the recipient is not driving).\n"
    "\n"
    "Boundary rules (apply consistently - HIGH is high-precision, borderline defaults to MEDIUM):\n"
    "  - Stating availability with no explicit 'please book/confirm' -> MEDIUM.\n"
    "  - 'FYI' / 'attached please find' with no request -> MEDIUM (LOW is only automated/social).\n"
    "  - Judge the WHOLE thread, not just the newest message.\n"
    "  - Mostly-social email with one minor ask -> MEDIUM (only a significant request is HIGH).\n"
    "\n"
    "Judge from the email's content only. Ignore dates and deadlines - a separate layer handles timing."
)

_SCHEMA = {"type": "array", "items": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]}}

csv.field_size_limit(sys.maxsize)  # message bodies exceed the default field cap


def _rows(source: Path):
    """Yield the raw `message` field from emails.csv, whether passed as .csv or .zip."""
    if source.suffix == ".zip":
        with zipfile.ZipFile(source) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".csv"))
            with archive.open(name) as handle:
                text = (line.decode("utf-8", "replace") for line in handle)
                for row in csv.DictReader(text):
                    yield row["message"]
    else:
        with source.open(encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                yield row["message"]


def _parse(raw: str) -> str:
    """Extract 'Subject + body' from a raw RFC-822 message; '' if there's no usable body."""
    message = message_from_string(raw)
    subject = message.get("Subject", "").strip()
    body = message.get_payload()
    if not isinstance(body, str):
        return ""
    text = f"{subject}\n{body}".strip()
    return text if len(text) > 20 else ""  # skip near-empty stubs


def _sample(source: Path, limit: int) -> list[str]:
    """Systematic sample (every Kth email) so labels span mailboxes, not just the first folder."""
    parsed = (t for t in (_parse(m) for m in _rows(source)) if t)
    stride = 300  # skip ahead so we cover the whole corpus, not one sender
    out: list[str] = []
    for i, text in enumerate(parsed):
        if i % stride == 0:
            out.append(text[:4000])  # cap length for the prompt
            if len(out) >= limit:
                break
    return out


def _label_batch(client: httpx.Client, emails: list[str], url: str) -> list[str] | None:
    """Label one batch; None if it can't be labeled after retries (caller skips it, keeps going)."""
    numbered = "\n\n".join(f"--- Email {i} ---\n{e}" for i, e in enumerate(emails))
    prompt = f"{_RUBRIC}\n\nReturn a JSON array of {len(emails)} labels, in order.\n\n{numbered}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": _SCHEMA},
    }
    for attempt in range(6):
        resp = client.post(url, headers={"x-goog-api-key": _API_KEY}, json=payload)
        if resp.status_code == 429:
            time.sleep(min(5 * (attempt + 1), 30))  # ramp up to 30s for sustained limits
            continue
        if resp.status_code >= 300:
            return None  # non-rate-limit error — skip this batch, don't kill the whole run
        labels = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
        return [str(x).lower() for x in labels]
    return None  # still rate-limited after all retries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="emails.csv or archive.zip")
    parser.add_argument("--limit", type=int, default=1500)
    parser.add_argument("--batch-size", type=int, default=20)  # fewer calls -> less rate-limit pressure
    parser.add_argument("--out", default="labeled.csv")
    parser.add_argument("--model", default=_DEFAULT_MODEL, help="Gemini model for labeling")
    args = parser.parse_args()

    if not _API_KEY:
        raise SystemExit("no GEMINI_API_KEY / GOOGLE_API_KEY in ../.env")
    url = _URL_TEMPLATE.format(model=args.model)
    print(f"labeling with {args.model}", flush=True)

    print(f"sampling up to {args.limit} emails from {args.source}...", flush=True)
    emails = _sample(Path(args.source), args.limit)
    print(f"parsed {len(emails)} emails; labeling in batches of {args.batch_size}...", flush=True)

    # Append each batch as it's labeled so a crash / rate-limit stop keeps everything so far.
    out_path = Path(args.out)
    written = 0
    with out_path.open("w", newline="", encoding="utf-8") as handle, httpx.Client(timeout=60) as client:
        writer = csv.writer(handle)
        writer.writerow(["text", "label"])
        for start in range(0, len(emails), args.batch_size):
            batch = emails[start : start + args.batch_size]
            labels = _label_batch(client, batch, url)
            if labels is None:
                print(f"  skipped batch at {start} (rate-limited/error) — keeping progress", flush=True)
                continue
            for text, label in zip(batch, labels):
                if label in ("low", "medium", "high"):
                    writer.writerow([text, label])
                    written += 1
            handle.flush()
            print(f"  labeled {min(start + args.batch_size, len(emails))}/{len(emails)} (saved {written})", flush=True)

    print(f"done — wrote {written} labeled rows to {out_path}", flush=True)


if __name__ == "__main__":
    main()
