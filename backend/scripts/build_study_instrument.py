"""Build the priority-calibration study instrument from the labelled holdout and stored drafts.

Emits a markdown document ready to be transcribed into a form, plus an answer key held in a
separate file the instrument never references. The split is structural: the participant-facing
document must not contain gold labels, and keeping them in one file with a "don't show this bit"
comment is how that goes wrong.

Part 1 items are the nine rows chosen in specs/features/priority-calibration-study.md. The row
indices live in this script rather than being re-derived, because the spec records them as the
join key for recomputing the model's predictions on exactly those items.

Output contains unmasked Enron text and is gitignored, like every other corpus artefact here.

Usage (from backend/):
    python scripts/build_study_instrument.py                    # Part 1 only
    python scripts/build_study_instrument.py --with-part2       # adds draft ratings from the DB
"""

import argparse
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_sessionmaker

csv.field_size_limit(10**9)

# Chosen 2026-09-12 by reading candidates, not sampling: the boundary rules are the point, and a
# random draw from a 46/46/28 distribution returns mostly easy cases. Rationale per item is in the
# spec; the note here is what a participant-blind reviewer needs to check coverage.
PART1_ROWS: list[tuple[int, str]] = [
    (3, "anchor: unambiguous direct request"),
    (8, "anchor: explicit obligation, model under-escalates"),
    (17, "boundary: FYI with no request"),
    (53, "boundary: mostly social, one minor ask"),
    (64, "anchor: pure marketing"),
    (77, "boundary: soft review request"),
    (91, "boundary: request buried in quoted history"),
    (110, "boundary: automated mail that needs action"),
    (2, "boundary: several soft requests"),
]

CONSENT = """## Before you start

Thank you for helping with this project.

**What this is.** We are building an email assistant that sorts incoming mail by how urgently it
needs attention. We want to know how *people* sort the same emails, so we can tell whether the
system's judgement is reasonable or just self-consistent.

**What you will do.** Two short parts, about 15 minutes in total.

1. Read 9 emails and sort each into high, medium or low urgency.
2. Read some AI-written replies and say whether each is good enough to send.

**What we collect.** Your answers, and your job role in general terms (for example "student",
"engineer", "administrator"). **We do not collect your name, your email address, or anything else
that identifies you.** Responses are given a number, not a name.

**The emails you will read are real but public.** They come from the Enron corpus, a dataset of
company emails released publicly during a US legal case and used widely in research. They are not
anyone's private mail, and they are not from anyone involved in this project. Some contain ordinary
business details such as names and phone numbers. They are shown unedited because the system was
measured on the unedited text, and editing them would break that comparison.

**Your answers are not a test.** There are no right answers. Where you disagree with us or with
each other, that disagreement is the result we are looking for.

**You can stop at any time**, and you can skip any question. If you stop partway, we keep whatever
you finished unless you tell us otherwise.

**Where it goes.** Summary figures appear in our final report. Individual responses do not, and the
raw responses are not published.

Questions: contact the project team.

---

**Do you consent to take part on this basis?**

- [ ] Yes, I consent
- [ ] No

*(If no, please close this form. Nothing is recorded.)*
"""

PART1_HEADER = """
---

# Part 1 — Sorting emails by urgency

You will read 9 emails. For each one, decide how urgently it needs the recipient's attention.

**Use your own judgement.** We deliberately have not given you a rulebook, because we want to know
how people sort these naturally.

A rough guide only:

- **High** — needs action soon, and something goes wrong if it is missed
- **Medium** — needs attention, but not immediately
- **Low** — can wait, or needs nothing at all

Two questions follow the emails.
"""

PART1_CLOSING = """
---

## Two last questions on Part 1

**Q1. Did any of those 9 emails not fit into high, medium or low?**
If yes, which one, and what was missing?

*(Free text)*

**Q2. Imagine you could mark certain senders as important, so mail from them was always treated as
urgent. Would that have changed how you sorted any of the emails above?**
If yes, which ones, and why?

*(Free text)*
"""

PART2_HEADER = """
---

# Part 2 — Rating AI-written replies

Below are replies our system drafted automatically. For each one, say whether you would be willing
to send it as written.

The original email is shown first, then the draft reply.

For each, answer:

- **Would you send this as written?** Yes / No / Only after editing
- **If no, or only after editing — what is wrong with it?** *(Free text)*

Personal details in these replies have been masked before the AI ever saw them, so you may see
placeholders like `[EMAIL_REDACTED]`. That is expected, not an error.
"""


def read_holdout(path: Path, rows: list[int]) -> dict[int, tuple[str, str]]:
    """(text, gold_label) per requested row index. Index is the position in the file."""
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        all_rows = list(csv.DictReader(handle))
    wanted = set(rows)
    found = {
        index: (row["text"], (row.get("label") or "").strip().lower())
        for index, row in enumerate(all_rows)
        if index in wanted
    }
    missing = wanted - found.keys()
    if missing:
        raise SystemExit(f"rows not found in {path}: {sorted(missing)} (file has {len(all_rows)})")
    return found


def render_part1(items: dict[int, tuple[str, str]]) -> str:
    blocks = [PART1_HEADER]
    for position, (row, _) in enumerate(PART1_ROWS, 1):
        body, _gold = items[row]
        blocks.append(
            f"\n---\n\n### Email {position} of 9\n\n"
            f"```\n{body.strip()}\n```\n\n"
            f"**How urgent is this email?**\n\n"
            f"- [ ] High\n- [ ] Medium\n- [ ] Low\n"
        )
    blocks.append(PART1_CLOSING)
    return "\n".join(blocks)


def render_key(items: dict[int, tuple[str, str]]) -> str:
    """Answer key. Never referenced by the instrument; kept in its own file deliberately."""
    lines = [
        "# Answer key — do NOT show participants",
        "",
        "Gold labels for the 9 Part-1 items, with the holdout row index as the join key for",
        "recomputing the model's predictions on exactly these items.",
        "",
        "| Position | Holdout row | Gold | Why chosen |",
        "|----------|-------------|------|------------|",
    ]
    for position, (row, why) in enumerate(PART1_ROWS, 1):
        _body, gold = items[row]
        lines.append(f"| {position} | {row} | {gold} | {why} |")
    counts: dict[str, int] = {}
    for row, _ in PART1_ROWS:
        counts[items[row][1]] = counts.get(items[row][1], 0) + 1
    spread = ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    lines += ["", f"Gold spread: {spread}.", "",
              "Deliberately not proportional to the holdout's 46 low / 46 medium / 28 high — the",
              "instrument tests the boundary rules, and a proportional draw returns mostly easy cases."]
    return "\n".join(lines) + "\n"


_DRAFTS = text("""
    select id, body_masked, draft_reply, critic_confidence, needs_human_review
    from messages
    where coalesce(draft_reply, '') <> ''
    order by critic_confidence nulls first, id
""")


async def load_drafts() -> list[dict]:
    async with get_sessionmaker()() as session:
        rows = (await session.execute(_DRAFTS)).mappings().all()
    return [dict(row) for row in rows]


def render_part2(drafts: list[dict]) -> tuple[str, str]:
    blocks = [PART2_HEADER]
    key = ["", "## Part 2 key — do NOT show participants", "",
           "| Position | Message id | Critic confidence | Flagged for review |",
           "|----------|------------|-------------------|--------------------|"]
    for position, row in enumerate(drafts, 1):
        source = (row["body_masked"] or "").strip()
        blocks.append(
            f"\n---\n\n### Reply {position} of {len(drafts)}\n\n"
            f"**The email received:**\n\n```\n{source}\n```\n\n"
            f"**The draft reply:**\n\n```\n{(row['draft_reply'] or '').strip()}\n```\n\n"
            f"**Would you send this as written?**\n\n"
            f"- [ ] Yes\n- [ ] Only after editing\n- [ ] No\n\n"
            f"**If no or only after editing, what is wrong with it?**\n\n*(Free text)*\n"
        )
        confidence = row["critic_confidence"]
        shown = "null" if confidence is None else f"{confidence:.2f}"
        key.append(f"| {position} | {row['id']} | {shown} | {row['needs_human_review']} |")
    return "\n".join(blocks), "\n".join(key) + "\n"


def report_threshold_coverage(drafts: list[dict]) -> None:
    """The spec requires >=5 drafts either side of 0.8, or the threshold cannot be tested."""
    scored = [d["critic_confidence"] for d in drafts if d["critic_confidence"] is not None]
    below = sum(1 for c in scored if c < 0.8)
    above = len(scored) - below
    distinct = sorted({round(c, 2) for c in scored})
    print(f"  part 2: {len(drafts)} draft(s), {below} below 0.8, {above} at or above")
    print(f"  distinct confidence values: {distinct}")
    if below < 5 or above < 5:
        print("  WARNING: the spec's 5-either-side condition is not met.")
        print("  Part 2 cannot test the 0.8 threshold. Report it as 'does confidence discriminate")
        print("  at all' and record the reason, per the spec's edge case.")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", default="holdout_to_label.csv")
    parser.add_argument("--out", default="study_instrument.md")
    parser.add_argument("--key-out", default="study_answer_key.md")
    parser.add_argument("--with-part2", action="store_true",
                        help="include draft ratings (needs a live DB)")
    args = parser.parse_args()

    items = read_holdout(Path(args.holdout), [row for row, _ in PART1_ROWS])
    document = CONSENT + render_part1(items)
    key = render_key(items)

    if args.with_part2:
        drafts = await load_drafts()
        if not drafts:
            raise SystemExit("no stored drafts — run scripts/generate_pending.py first")
        part2, part2_key = render_part2(drafts)
        document += part2
        key += part2_key
        report_threshold_coverage(drafts)

    Path(args.out).write_text(document, encoding="utf-8")
    Path(args.key_out).write_text(key, encoding="utf-8")
    print(f"  wrote {args.out} ({len(document.splitlines())} lines)")
    print(f"  wrote {args.key_out} — keep this away from participants")


if __name__ == "__main__":
    asyncio.run(main())
