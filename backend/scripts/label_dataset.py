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
_MODEL = "gemini-3.5-flash-lite"
_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{_MODEL}:generateContent"

_RUBRIC = (
    "Label each email HIGH, MEDIUM, or LOW by how much it needs the recipient to ACT:\n"
    "- HIGH: asks for a reply, decision, approval, or names a deadline.\n"
    "- MEDIUM: relevant/informative but needs no direct action.\n"
    "- LOW: FYI, newsletter, automated, or social chit-chat.\n"
    "Judge the email's inherent importance, not any date it happens to mention."
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


def _label_batch(client: httpx.AsyncClient, emails: list[str]) -> list[str]:
    numbered = "\n\n".join(f"--- Email {i} ---\n{e}" for i, e in enumerate(emails))
    prompt = f"{_RUBRIC}\n\nReturn a JSON array of {len(emails)} labels, in order.\n\n{numbered}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": _SCHEMA},
    }
    for attempt in range(4):
        resp = client.post(_URL, headers={"x-goog-api-key": _API_KEY}, json=payload)
        if resp.status_code == 429 and attempt < 3:
            time.sleep(3 * (attempt + 1))
            continue
        resp.raise_for_status()
        labels = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
        return [str(x).lower() for x in labels]
    resp.raise_for_status()
    return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="emails.csv or archive.zip")
    parser.add_argument("--limit", type=int, default=1500)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--out", default="labeled.csv")
    args = parser.parse_args()

    if not _API_KEY:
        raise SystemExit("no GEMINI_API_KEY / GOOGLE_API_KEY in ../.env")

    print(f"sampling up to {args.limit} emails from {args.source}...")
    emails = _sample(Path(args.source), args.limit)
    print(f"parsed {len(emails)} emails; labeling in batches of {args.batch_size}...")

    rows: list[tuple[str, str]] = []
    with httpx.Client(timeout=60) as client:
        for start in range(0, len(emails), args.batch_size):
            batch = emails[start : start + args.batch_size]
            labels = _label_batch(client, batch)
            for text, label in zip(batch, labels):
                if label in ("low", "medium", "high"):
                    rows.append((text, label))
            print(f"  labeled {min(start + args.batch_size, len(emails))}/{len(emails)}")

    out_path = Path(args.out)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["text", "label"])
        writer.writerows(rows)

    counts = {label: sum(1 for _, x in rows if x == label) for label in ("low", "medium", "high")}
    print(f"wrote {len(rows)} labeled rows to {out_path} — distribution: {counts}")


if __name__ == "__main__":
    main()
