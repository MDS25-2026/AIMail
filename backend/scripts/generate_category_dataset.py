"""Synthetic B2B email dataset generator for the 6-category taxonomy (#141).

Generates a balanced dataset of realistic B2B emails using Gemini Flash, structured
across Han's 6-category taxonomy:
  1. client: Client / Customer (deals, onboarding, customer support, sales)
  2. vendor: Vendor / Partner (procurement, SaaS renewals, invoices, partner integrations)
  3. internal: Internal / Team (sprint standups, PR reviews, 1-on-1s, engineering syncs)
  4. security: Security / Compliance (SOC 2, audits, access reviews, vulnerability alerts, NDAs)
  5. admin: Admin / Logistics (all-hands, room bookings, office ops, travel itineraries)
  6. personal: Personal / Social (coffee catchups, lunch chats, celebrations, informal banter)

Each sample naturally incorporates Presidio-style PII tokens ([PERSON_1], [ORG_1], [EMAIL_1],
[DATE_1], [PHONE_1], [MONEY_1]) to match the exact masked distribution produced by Lane A.

Outputs:
  - backend/data/category/train.csv: 600 emails (100 per category)
  - backend/data/category/holdout_gold.csv: 120 emails (20 per category for human verification)

Usage:
  python scripts/generate_category_dataset.py [--train-count 100] [--gold-count 20]
"""

import argparse
import csv
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Load repo-root environment
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")

_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
_DEFAULT_MODEL = "gemini-3.5-flash"
_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

CATEGORIES = [
    "client",
    "vendor",
    "internal",
    "security",
    "admin",
    "personal",
]

CATEGORY_DESCRIPTIONS = {
    "client": (
        "Client / Customer: External customer relationships, prospective deals, sales proposals, "
        "enterprise tier renewals, customer support bug reports, onboarding questions, and SLA reviews."
    ),
    "vendor": (
        "Vendor / Partner: External third-party software subscriptions, SaaS tool renewal notices, "
        "procurement terms, vendor invoices, payment confirmations, partner API integrations, and RFP updates."
    ),
    "internal": (
        "Internal / Team: Peer-to-peer engineering collaboration, sprint retrospectives, PR code reviews, "
        "standup blockers, product roadmaps, 1-on-1 rescheduling, and cross-team design discussions."
    ),
    "security": (
        "Security / Compliance: SOC 2 and ISO 27001 audit evidence requests, penetration test disclosures, "
        "access permission reviews, legal NDAs, employee security awareness, phishing drills, and policy sign-offs."
    ),
    "admin": (
        "Admin / Logistics: Company-wide all-hands announcements, conference room reservations, catering orders, "
        "office holiday schedules, corporate flight/travel itineraries, hardware laptop provisioning, and facility updates."
    ),
    "personal": (
        "Personal / Social: Casual non-work conversations between coworkers, coffee chat invites, birthday greetings, "
        "farewell cards, team lunch banter, weekend plans, and casual non-urgent check-ins."
    ),
}

PROMPT_SUBCATEGORIES = {
    "client": [
        "enterprise sales pricing and license seat expansion request",
        "customer support escalation regarding API latency and timeout errors",
        "new prospect requesting product demo and enterprise security overview",
        "contract SLA breach discussion and compensation credit request",
        "client customer onboarding milestone sign-off and kickoff call",
        "renewal quotation with request for multi-year payment discount",
    ],
    "vendor": [
        "annual SaaS subscription renewal notice with updated license terms",
        "vendor invoice submission with payment remittance instructions",
        "cloud infrastructure usage overage alert and capacity planning",
        "third-party consulting firm submitting statement of work (SOW)",
        "API technology partner requesting co-marketing integration sync",
        "procurement master service agreement (MSA) redline review",
    ],
    "internal": [
        "sprint planning blocker update and backend dependencies sync",
        "pull request code review comments on database migration and ORM schema",
        "weekly engineering 1-on-1 rescheduling and agenda items",
        "product manager sharing Q4 feature roadmap priorities and timeline",
        "staging environment outage investigation and post-mortem review",
        "QA test automation failure report and bug triage notes",
    ],
    "security": [
        "annual SOC 2 Type II audit evidence collection checklist",
        "critical vulnerability disclosure notification and emergency patch schedule",
        "quarterly employee IAM access privilege review and re-certification",
        "mutual non-disclosure agreement (NDA) countersignature request",
        "phishing simulation test results and security awareness training reminder",
        "data processing addendum (DPA) compliance review for international transfers",
    ],
    "admin": [
        "all-hands quarterly company town hall meeting agenda and dial-in details",
        "executive boardroom booking confirmation and AV equipment setup",
        "office facilities announcement regarding HVAC maintenance and floor closure",
        "corporate travel flight confirmation and hotel receipt for offsite",
        "IT hardware laptop replacement delivery and asset return instructions",
        "company holiday calendar and public holiday office closure notice",
    ],
    "personal": [
        "informal invitation to grab coffee downstairs before standup",
        "organizing a farewell lunch for a departing colleague next Friday",
        "birthday wishes and sharing virtual celebration card link",
        "casual conversation about weekend hiking plans and restaurant recommendations",
        "congratulations on work anniversary and quick watercooler greeting",
        "team social trivia night RSVP and casual catchup",
    ],
}


def _build_prompt(category: str, subtopic: str, batch_size: int) -> str:
    desc = CATEGORY_DESCRIPTIONS[category]
    return f"""You are generating realistic, varied corporate business emails for machine learning classification.

Target Category: {category}
Description: {desc}
Specific Sub-topic focus: {subtopic}

Generate exactly {batch_size} distinct, realistic emails belonging strictly to the category '{category}'.

Formatting and realism rules:
1. Include a realistic subject line and body text (2 to 5 paragraphs or bullet points).
2. Format realistic corporate sign-offs, email headers, or thread context where appropriate.
3. Use realistic redaction tokens where personal names, phone numbers, external organizations, or dates appear, matching Presidio NER output:
   - Use [PERSON_1], [PERSON_2] for people names
   - Use [ORG_1], [ORG_2] for company/organization names
   - Use [EMAIL_1], [EMAIL_2] for email addresses
   - Use [DATE_1], [DATE_2] for specific calendar dates
   - Use [MONEY_1] for monetary figures ($5,000, etc.)
   - Use [PHONE_1] for phone numbers
4. Ensure emails sound natural, realistic, and representative of modern enterprise corporate work.

Return ONLY a JSON array of objects with the structure:
[
  {{
    "subject": "Subject line text",
    "body": "Full email body text including greeting, body paragraphs, and sign-off",
    "category": "{category}"
  }}
]"""


def _generate_batch(client: httpx.Client, category: str, subtopic: str, batch_size: int = 5) -> list[dict]:
    """Call Gemini to generate a batch of structured emails."""
    if not _API_KEY:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY environment variable is missing.")

    prompt = _build_prompt(category, subtopic, batch_size)
    url = _URL_TEMPLATE.format(model=_DEFAULT_MODEL) + f"?key={_API_KEY}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.85,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(4):
        try:
            resp = client.post(url, json=payload, timeout=60.0)
            if resp.status_code == 429:
                wait_time = 2.0 ** (attempt + 1)
                logger.warning("Rate limited (429). Backing off for %.1fs...", wait_time)
                time.sleep(wait_time)
                continue
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            items = json.loads(raw_text)
            if isinstance(items, list):
                valid = []
                for item in items:
                    sub = item.get("subject", "").strip()
                    body = item.get("body", "").strip()
                    if sub and body:
                        combined = f"Subject: {sub}\n\n{body}"
                        valid.append({"text": combined, "category": category})
                return valid
        except Exception as exc:
            logger.warning("Batch generation attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2.0)

    logger.error("Failed to generate batch for %s after 4 attempts", category)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic B2B email taxonomy dataset.")
    parser.add_argument("--train-count", type=int, default=100, help="Train emails per category (default: 100)")
    parser.add_argument("--gold-count", type=int, default=20, help="Holdout gold emails per category (default: 20)")
    parser.add_argument("--model", default=_DEFAULT_MODEL, help="Gemini model name")
    parser.add_argument("--out-dir", default="data/category", help="Output directory")
    args = parser.parse_args()

    total_per_cat = args.train_count + args.gold_count
    out_dir = Path(__file__).resolve().parent.parent / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Generating dataset: %d train + %d gold per category (%d total per category across 6 categories = %d)",
                args.train_count, args.gold_count, total_per_cat, total_per_cat * len(CATEGORIES))

    all_samples: list[dict] = []

    with httpx.Client() as client:
        for cat in CATEGORIES:
            subtopics = PROMPT_SUBCATEGORIES[cat]
            cat_samples: list[dict] = []
            logger.info("Generating emails for category: '%s'...", cat)

            while len(cat_samples) < total_per_cat:
                needed = total_per_cat - len(cat_samples)
                batch_size = min(6, needed)
                subtopic = random.choice(subtopics)
                items = _generate_batch(client, cat, subtopic, batch_size=batch_size)
                if not items:
                    logger.warning("Empty batch received for %s. Retrying...", cat)
                    time.sleep(1.0)
                    continue

                for item in items:
                    cat_samples.append(item)
                    if len(cat_samples) >= total_per_cat:
                        break

                logger.info("  [%s] Generated %d / %d emails", cat, len(cat_samples), total_per_cat)
                time.sleep(0.5)  # respectful pacing between calls

            all_samples.extend(cat_samples)

    # Partition into stratified train and holdout gold sets
    train_rows: list[dict] = []
    gold_rows: list[dict] = []

    for cat in CATEGORIES:
        cat_items = [s for s in all_samples if s["category"] == cat]
        random.shuffle(cat_items)
        gold_rows.extend(cat_items[:args.gold_count])
        train_rows.extend(cat_items[args.gold_count:args.gold_count + args.train_count])

    random.shuffle(train_rows)
    random.shuffle(gold_rows)

    # Write train.csv
    train_path = out_dir / "train.csv"
    with train_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "category"])
        writer.writeheader()
        writer.writerows(train_rows)
    logger.info("Wrote %d training rows to %s", len(train_rows), train_path)

    # Write holdout_gold.csv (with category populated for evaluation)
    gold_path = out_dir / "holdout_gold.csv"
    with gold_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "category"])
        writer.writeheader()
        writer.writerows(gold_rows)
    logger.info("Wrote %d holdout gold rows to %s", len(gold_rows), gold_path)

    # Write audit inspection sheet holdout_audit.csv with a reviewer column
    audit_path = out_dir / "holdout_audit.csv"
    reviewers = ["Han", "JJ", "Hanif"]
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "assigned_reviewer", "category", "verified_category", "notes", "text"])
        writer.writeheader()
        for idx, row in enumerate(gold_rows, 1):
            rev = reviewers[(idx - 1) % len(reviewers)]
            writer.writerow({
                "id": idx,
                "assigned_reviewer": rev,
                "category": row["category"],
                "verified_category": row["category"],
                "notes": "",
                "text": row["text"],
            })
    logger.info("Wrote %d audit rows distributed among %s to %s", len(gold_rows), reviewers, audit_path)


if __name__ == "__main__":
    main()
