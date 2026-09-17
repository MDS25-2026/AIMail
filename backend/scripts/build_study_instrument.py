"""Build the priority-calibration study instrument from the labelled holdout and stored drafts.

Emits a markdown document ready to be transcribed into Microsoft Forms, plus an answer key held in
a separate file the instrument never references. The split is structural: the participant-facing
document must not contain gold labels, and keeping them in one file with a "don't show this bit"
comment is how that goes wrong.

Microsoft Forms over Google Forms deliberately — it is the institution's own tooling, so where the
responses are stored has a cleaner answer under PDPA. The heavier obligations should not attach at
all, since the instrument collects no personal data by design: one fixed-option question about
work-email experience, not a free-text role a participant could self-identify in.

That question is also a validity control, not a demographic. The corpus is workplace email and the
classifier is for workplace triage, so a human ceiling measured on people who have never managed a
work inbox is a ceiling for the wrong population. Recording the spread lets the report say which
population the number describes.

Part 1 items are the nine rows chosen in specs/features/priority-calibration-study.md. The row
indices live in this script rather than being re-derived, because the spec records them as the
join key for recomputing the model's predictions on exactly those items.

Output contains unmasked Enron text and is gitignored, like every other corpus artefact here.

Writes three files: the participant-facing instrument, the answer key, and a transcription guide
for Microsoft Forms. Forms has no supported creation API — Graph's Forms API reads responses from
forms that already exist — so the guide makes the manual build mechanical instead: paste-ready
option blocks, the repeated Part 2 block printed once, and the mapping from Forms' exported column
names to the ones analyse_study.py expects.

Usage (from backend/):
    python scripts/build_study_instrument.py                    # Part 1 only
    python scripts/build_study_instrument.py --with-part2       # adds draft ratings from the DB
"""

import argparse
import asyncio
import csv
import re
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

We are building an email assistant that sorts mail by how urgently it needs attention. We want to
know how *people* sort the same emails, so we can tell whether the system's judgement is reasonable
or just self-consistent.

**What you will do.** Read 9 emails and sort each as high, medium or low urgency, then rate a few
AI-written replies. About 20 minutes.

**What we collect.** Your answers, plus one multiple-choice question about how much work email you
deal with. **No name, no email address, no ID number.** Responses are numbered, not named — we
cannot tell which one is yours.

**The emails are real but public.** They come from the Enron corpus, a public research dataset from
a US court case. They are not anyone's private mail and have nothing to do with anyone on this
project.

**There are no right answers.** Where you disagree with us, or with each other, that disagreement
is exactly what we are looking for.

You can skip any question or stop at any time. Summary figures go in our report; raw responses do
not, and they are deleted once it is submitted. Any questions, reply to whoever sent you this link.

---

**Do you consent to take part on this basis?**

- [ ] Yes, I consent
- [ ] No

---

**How much experience do you have managing a work or professional email inbox?**

- [ ] Little or none
- [ ] Some - an internship, part-time or casual work
- [ ] Regular - it is part of my current work
- [ ] Heavy - I deal with a large volume of work email daily
"""

PART1_HEADER = """
---

# Part 1 — Sorting emails by urgency

### A little context first

These emails are from **Enron**, an American company based in Houston, Texas, written between
roughly 1999 and 2001. At the time it was one of the largest companies in the United States —
around 20,000 employees, with offices across America, Europe and Asia.

**What the company did.** Enron began as a natural gas pipeline business. By the time these emails
were written it had become mainly an energy *trading* company: it bought gas and electricity from
producers and sold it on to utilities, factories and other large users, making its money on the
difference and on managing the risk in between. It still owned physical assets — pipelines, power
plants — but trading was the centre of the business.

**What that looked like day to day.** Traders agreed contracts with other companies to deliver a
quantity of gas or electricity, at an agreed price, on agreed dates — sometimes for the next day,
sometimes years ahead. Around them sat analysts pricing those deals, schedulers arranging the
physical delivery, risk managers tracking how exposed the company was, and lawyers and accountants
handling the paperwork. In 1999 Enron launched an online trading platform that let other companies
deal with it directly through a website, which pushed the volume up enormously.

Enron was also heavily involved in California's electricity market during the power shortages there
in 2000 and 2001, which comes up in some of the mail.

**Whose inboxes these are.** The archive holds the mailboxes of roughly 150 employees, mostly
traders and their managers in the Houston gas and power groups. So most of what you will read is
one colleague writing to another about a deal, a report, a meeting, or an approval someone needs.
A few are newsletters or automated notices from internal systems.

The company collapsed at the end of 2001. A US regulator released these emails during the
investigation that followed, which is why they can be used for research.

**Read each one as the person who received it:** an employee going through their own work inbox on
a normal working day.

**Abbreviations you will see:**

- **EOL** — EnronOnline, the company's electronic trading platform
- **ECT** — Enron Capital & Trade, a division of the company. **ENA** — Enron North America
- **HOU**, **DEN** — office locations, Houston and Denver. Internal addresses look like
  `Phillip K Allen/HOU/ECT`
- **MW** — megawatts, a unit of electricity
- **CAISO** — the body that runs California's electricity grid
- **a "book"** — the set of trades a particular desk or region is responsible for

You will not recognise everything — deal names, system names, people you have never heard of. That
is expected. You do not need to understand every term to get a sense of how much attention an email
needs.

---

You will read 9 emails. For each one, decide how urgently it needs the recipient's attention.

**Use your own judgement.** We have deliberately not defined high, medium or low, because we want
to know how people sort these naturally rather than whether they can follow our definitions. Sort
them the way you would if this were your inbox.

**They will look inconsistent, and that is not a mistake.** These are real emails pulled from an
archive exactly as they were stored. Some show who sent them and a subject line; some are just the
message. Some are forwards with the older thread underneath. Judge each on what is actually in
front of you — if you cannot tell who sent it, that is part of the situation.

Two questions follow the emails.
"""

# Positions (not row indices) where we ask for reasoning. Chosen because these three are where
# disagreement is most informative: 4 is the item whose gold label contradicts the written rubric,
# 7 hides its request in quoted history, and 8 is the one the model got confidently wrong.
# Asking on all nine would triple the completion time for diminishing returns.
EXPLAIN_POSITIONS = (4, 7, 8)

EXPLAIN_PROMPT = """
**In one or two sentences: what made you choose that?**

*(Free text. There is no right answer — we are asking because this email is one people tend to
read differently.)*
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

Below are replies our system drafted automatically. The email it was replying to is shown first,
then the draft.

For each one you will answer four quick yes/no checks and then an overall verdict. The four checks
are the same ones our system runs on itself — we want to know where your judgement and its
judgement differ, not just whether they agree overall.

Personal details were removed before the AI ever saw these emails, so you may see placeholders like
`[EMAIL_REDACTED]`. That is expected, not an error.
"""

# Plain-language wording of the four gates the critic already computes. Deliberately not the
# internal names: asking "is grounding_ok" would get a shrug, and the point is to compare a human
# judgement against each gate separately. #78 requires exactly this — one overall verdict hides
# which gate carries signal.
PART2_GATES = """
**1. Does the reply state anything that is not in the email above?**
Made-up facts, dates, names, or promises that were never mentioned.

- [ ] No, everything in it traces back to the email
- [ ] Yes, it invents something
- [ ] Not sure

**2. Does the reply give away any personal details it should not?**
A phone number, email address, ID number, or someone else's name.

- [ ] No
- [ ] Yes
- [ ] Not sure

**3. Is the tone right for a work reply?**

- [ ] Yes
- [ ] Too formal
- [ ] Too casual
- [ ] Something else is off

**4. Does the reply answer everything the email asked?**

- [ ] Yes, all of it
- [ ] It misses part of it
- [ ] It misses most of it

**Overall: would you send this as written?**

- [ ] Yes
- [ ] Only after editing
- [ ] No

**If not as written, what would you change?**

*(Free text, optional)*
"""


# A line this long that does not end a sentence was almost certainly wrapped by the sender's mail
# client, not broken deliberately. Shorter lines — headers, signatures, phone numbers — keep their
# break because there the break carries meaning.
_WRAPPED_MIN_CHARS = 55
_SENTENCE_END = (".", "?", "!", ":", ";", ",", "-")

# A header line never continues into the next one, however long it is: "To: <many recipients>"
# does not end in punctuation and would otherwise swallow the "cc:" and "Subject:" lines after it.
_HEADER_LINE = re.compile(r"^(to|from|cc|bcc|subject|date|sent|reply-to)\s*:", re.IGNORECASE)


def readable_email(text: str) -> str:
    """Unwrap 2000-era hard wrapping, and make every real break a blank line.

    Microsoft Forms discards single newlines on paste and keeps blank lines, so an email pasted
    raw arrives as one run-on block — "Thanks in advance.Mick Walters3-4783". Re-flowing here is
    presentational only: not a word changes, so the text stays comparable with what the classifier
    was measured on.
    """
    paragraphs = []
    for block in re.split(r"\n\s*\n", (text or "").replace("\t", " ")):
        lines = [re.sub(r" +", " ", line).strip() for line in block.split("\n")]
        lines = [line for line in lines if line]
        if not lines:
            continue
        merged: list[str] = []
        for line in lines:
            wrapped = (
                merged
                and len(merged[-1]) >= _WRAPPED_MIN_CHARS
                and not merged[-1].endswith(_SENTENCE_END)
                and not _HEADER_LINE.match(merged[-1])
                and not _HEADER_LINE.match(line)
            )
            if wrapped:
                merged[-1] = f"{merged[-1]} {line}"
            else:
                merged.append(line)
        paragraphs.extend(merged)
    return "\n\n".join(paragraphs)


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
        block = (
            f"\n---\n\n### Email {position} of 9\n\n"
            f"```\n{readable_email(body)}\n```\n\n"
            f"**How urgent is this email?**\n\n"
            f"- [ ] High\n- [ ] Medium\n- [ ] Low\n"
        )
        if position in EXPLAIN_POSITIONS:
            block += EXPLAIN_PROMPT
        blocks.append(block)
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
    select id, body_masked, draft_reply, critic_confidence, needs_human_review, critic_checks
    from messages
    where coalesce(draft_reply, '') <> ''
    order by critic_confidence nulls first, id
""")


async def load_drafts() -> list[dict]:
    async with get_sessionmaker()() as session:
        rows = (await session.execute(_DRAFTS)).mappings().all()
    return [dict(row) for row in rows]


def _first_reason(draft: dict) -> str:
    reasons = (draft.get("critic_checks") or {}).get("review_reasons") or []
    return reasons[0].split(":")[0] if reasons else ""


def select_drafts(drafts: list[dict], limit: int) -> list[dict]:
    """Spread the sample across distinct flag reasons, with unflagged drafts as controls.

    Rating all of them would take longer than the rest of the instrument combined, and a sample of
    near-identical passes teaches nothing. Every gate we want to test needs at least one draft the
    critic flagged on that ground, and at least one it did not, or a disagreement is unreadable.
    """
    flagged = [d for d in drafts if d["needs_human_review"]]
    clean = [d for d in drafts if not d["needs_human_review"]]

    # Controls are reserved first, not added after. Filling on distinct flag reasons alone consumes
    # every slot, and a sample with no unflagged draft cannot distinguish a participant who says
    # "fine" to everything from a critic that flags nothing.
    controls = min(len(clean), max(1, limit // 3)) if clean else 0
    chosen = clean[:controls]

    seen: set[str] = set()
    for draft in flagged:
        if len(chosen) >= limit:
            break
        reason = _first_reason(draft)
        if reason not in seen:
            seen.add(reason)
            chosen.append(draft)

    remaining = [d for d in flagged + clean if d not in chosen]
    chosen.extend(remaining[: max(0, limit - len(chosen))])
    return chosen[:limit]


def render_part2(drafts: list[dict]) -> tuple[str, str]:
    blocks = [PART2_HEADER]
    key = ["", "## Part 2 key — do NOT show participants", "",
           "Gate answers map to the critic's own checks: Q1 grounding_ok, Q2 pii_clean,",
           "Q3 tone_match, Q4 completeness. Compare each separately — one overall verdict",
           "hides which gate carries signal (#78).", "",
           "| Position | Message id | Confidence | Flagged | Critic's reason |",
           "|----------|------------|------------|---------|-----------------|"]
    for position, row in enumerate(drafts, 1):
        source = (row["body_masked"] or "").strip()
        blocks.append(
            f"\n---\n\n### Reply {position} of {len(drafts)}\n\n"
            f"**The email that was received:**\n\n```\n{source}\n```\n\n"
            f"**The draft reply:**\n\n```\n{readable_email(row["draft_reply"])}\n```\n"
            f"{PART2_GATES}"
        )
        confidence = row["critic_confidence"]
        shown = "null" if confidence is None else f"{confidence:.2f}"
        key.append(f"| {position} | {row['id']} | {shown} | {row['needs_human_review']} "
                   f"| {_first_reason(row) or '-'} |")
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


FORMS_INTRO = """# Transcription guide — Microsoft Forms

Microsoft Forms has no supported API for creating forms (Graph's Forms API reads responses from
forms that already exist), so this is built by hand. This guide makes that mechanical.

**Two tricks do most of the work:**

1. **Duplicate, do not retype.** Part 1 is the same question nine times and Part 2 is the same six
   questions repeated per draft. Build one, hit duplicate, swap the text.
2. **Paste option blocks whole.** Forms splits a multi-line paste into separate options, so paste
   all the choices at once instead of typing them one at a time.

**Before you start, in Settings:** turn OFF "Record name" — the study collects no identity, and a
form that records names contradicts the consent screen. Leave "One response per person" off too,
since that also keys on identity.

Realistically 20-30 minutes.

---

## Step 1 — Form title and description

**Title:** Sorting work email by urgency

**Description:** paste the consent text from `study_instrument.md` (everything above the first
`---`). Forms descriptions accept long text.

---

## Step 2 — Two opening questions

### Question: consent
Type: **Choice**, required.

> Do you consent to take part on this basis?

Options — paste as one block:

```
Yes, I consent
No
```

CSV column: `consent`

### Question: experience
Type: **Choice**, required.

> How much experience do you have managing a work or professional email inbox?

Options — paste as one block:

```
Little or none
Some - an internship, part-time or casual work
Regular - it is part of my current work
Heavy - I deal with a large volume of work email daily
```

CSV column: `role`

---

## Step 3 — Part 1, nine questions

Add a **section** first, titled "Part 1 - Sorting emails by urgency", and paste the Part 1 intro
text into the section description.

Build **question 1**, then duplicate it eight times and swap only the email text.

Type: **Choice**, required. Put the email text in the question's **subtitle** (the "..." menu on the
question gives you "Subtitle"), so the options stay readable.

> How urgent is this email?

Options — paste as one block:

```
High
Medium
Low
```

CSV columns: `item_1` through `item_9`, in the order below.

Three of them also need a follow-up **Text** question, long answer, optional:

> In one or two sentences: what made you choose that?

These go after items 4, 7 and 8. CSV columns: `explain_4`, `explain_7`, `explain_8`.

### The nine email texts, in order

**Paste these exactly as they appear, blank lines included.** Forms discards single line breaks and
keeps blank ones, and the Enron corpus is hard-wrapped by a 2000-era mail client — so pasting the
raw text arrives as a run-on block ("Thanks in advance.Mick Walters3-4783"). These have been
re-flowed so they survive. Do not close the gaps up.
"""

FORMS_CLOSING = """
---

## Step 4 — Two closing questions

Both **Text**, long answer, optional.

> Did any of those 9 emails not fit into high, medium or low? If yes, which one, and what was
> missing?

CSV column: `q1_not_fitting`

> Imagine you could mark certain senders as important, so mail from them was always treated as
> urgent. Would that have changed how you sorted any of the emails above? If yes, which ones,
> and why?

CSV column: `q2_sender_list`
"""

FORMS_PART2_INTRO = """
---

## Step 5 — Part 2, six drafts

Add a **section** titled "Part 2 - Rating AI-written replies" and paste the Part 2 intro into its
description.

**Build these six questions once**, then duplicate the whole block for each remaining draft and
swap the email and draft text in the subtitle.

Put the email and the draft in the **subtitle of the first question** of each block, so a
participant reads them once and answers six questions underneath.

### Question A — Choice, required
> Does the reply state anything that is not in the email above?

```
No, everything in it traces back to the email
Yes, it invents something
Not sure
```
CSV column: `g1_N`

### Question B — Choice, required
> Does the reply give away any personal details it should not?

```
No
Yes
Not sure
```
CSV column: `g2_N`

### Question C — Choice, required
> Is the tone right for a work reply?

```
Yes
Too formal
Too casual
Something else is off
```
CSV column: `g3_N`

### Question D — Choice, required
> Does the reply answer everything the email asked?

```
Yes, all of it
It misses part of it
It misses most of it
```
CSV column: `g4_N`

### Question E — Choice, required
> Overall: would you send this as written?

```
Yes
Only after editing
No
```
CSV column: `send_N`

### Question F — Text, long answer, optional
> If not as written, what would you change?

CSV column: `comment_N`

### The six email and draft pairs
"""


def render_forms_guide(items: dict[int, tuple[str, str]], drafts: list[dict]) -> str:
    blocks = [FORMS_INTRO]
    for position, (row, _) in enumerate(PART1_ROWS, 1):
        body, _gold = items[row]
        explain = "  **+ follow-up text question**" if position in EXPLAIN_POSITIONS else ""
        blocks.append(f"\n**item_{position}**{explain}\n\n```\n{readable_email(body)}\n```\n")
    blocks.append(FORMS_CLOSING)

    if not drafts:
        blocks.append("\n*(Part 2 omitted — rerun with --with-part2 to include it.)*\n")
        return "\n".join(blocks)

    blocks.append(FORMS_PART2_INTRO)
    for position, row in enumerate(drafts, 1):
        blocks.append(
            f"\n#### Draft {position}  (CSV columns g1_{position}..g4_{position}, "
            f"send_{position}, comment_{position})\n\n"
            f"**Email received:**\n\n```\n{readable_email(row["body_masked"])}\n```\n\n"
            f"**Draft reply:**\n\n```\n{readable_email(row["draft_reply"])}\n```\n"
        )

    mapping = ["\n---\n\n## Column mapping — check this after exporting\n",
               "Forms names its export columns after the question text, and `analyse_study.py`",
               "expects the short names below. Rename the header row once after export and the",
               "analysis runs without further editing.\n",
               "| Question | CSV column |", "|----------|------------|",
               "| *(add yourself: 1, 2, 3...)* | `participant` |",
               "| Consent | `consent` |", "| Work-email experience | `role` |"]
    for position in range(1, len(PART1_ROWS) + 1):
        mapping.append(f"| Part 1 email {position} | `item_{position}` |")
    for position in EXPLAIN_POSITIONS:
        mapping.append(f"| Reasoning after email {position} | `explain_{position}` |")
    mapping += ["| Did any not fit | `q1_not_fitting` |",
                "| Would a sender list change it | `q2_sender_list` |"]
    for position in range(1, len(drafts) + 1):
        mapping.append(
            f"| Draft {position}: invents / PII / tone / answers / overall / comment "
            f"| `g1_{position}` `g2_{position}` `g3_{position}` `g4_{position}` "
            f"`send_{position}` `comment_{position}` |"
        )
    mapping += ["", "`scripts/analyse_study.py --template` writes a blank CSV with exactly these",
                "column names, so you can diff the two header rows rather than checking by eye.",
                "",
                "Forms does not export a `participant` column. Number the rows 1, 2, 3 yourself —",
                "a sequential number, never anything derived from who they are."]
    blocks.append("\n".join(mapping) + "\n")
    return "\n".join(blocks)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", default="holdout_to_label.csv")
    parser.add_argument("--out", default="study_instrument.md")
    parser.add_argument("--key-out", default="study_answer_key.md")
    parser.add_argument("--with-part2", action="store_true",
                        help="include draft ratings (needs a live DB)")
    parser.add_argument("--part2-limit", type=int, default=6,
                        help="drafts to rate; 4 gate questions each, so this drives completion time")
    parser.add_argument("--forms-guide", default="study_forms_guide.md",
                        help="transcription guide for Microsoft Forms, written alongside the instrument")
    args = parser.parse_args()

    items = read_holdout(Path(args.holdout), [row for row, _ in PART1_ROWS])
    document = CONSENT + render_part1(items)
    key = render_key(items)
    drafts: list[dict] = []

    if args.with_part2:
        available = await load_drafts()
        if not available:
            raise SystemExit("no stored drafts — run scripts/generate_pending.py first")
        drafts = select_drafts(available, args.part2_limit)
        print(f"  selected {len(drafts)} of {len(available)} draft(s) for Part 2")
        part2, part2_key = render_part2(drafts)
        document += part2
        key += part2_key
        report_threshold_coverage(drafts)

    Path(args.out).write_text(document, encoding="utf-8")
    Path(args.key_out).write_text(key, encoding="utf-8")
    Path(args.forms_guide).write_text(render_forms_guide(items, drafts), encoding="utf-8")
    print(f"  wrote {args.out} ({len(document.splitlines())} lines)")
    print(f"  wrote {args.key_out} — keep this away from participants")
    print(f"  wrote {args.forms_guide} — paste-ready blocks and the export column mapping")


if __name__ == "__main__":
    asyncio.run(main())
