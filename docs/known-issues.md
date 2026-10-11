# Known issues — found after the 2026-08-26 audit

Defects and limitations discovered while testing the system, not covered by the original audit's
nine items (those live in [`audit-remediation-plan.md`](audit-remediation-plan.md)). Recorded so
they are addressed deliberately rather than rediscovered.

Each entry: what happens, why it happens if known, and how much it matters. Fixed entries are moved
to [Fixed](#fixed) with the pull request that fixed them, never deleted.

Last reviewed: 2026-10-11, against `main` at `a9a6af5`.

## Open

### Documents uploaded before 2026-10-04 are stored unmasked — Lane B
New uploads are masked (see Fixed). Documents ingested before that fix are stored as they were
uploaded. Re-upload them (or run `make ingest` again) so their chunks are replaced with masked ones.

### The critic has never been validated against human judgement — Lane C
The confidence score is emitted by the model itself and is not compared to any human rating, so
"below 0.8 is flagged" rests on an unmeasured signal. A small study — two people rating ~20 drafts
good/bad, compared against the critic's pass/fail — would convert the project's weakest claim into
a measured one. The planted-failure set in `backend/eval/critic/v1.json` measures the review gate's
recall on known failures; it does not measure agreement with a person's judgement of a whole draft.

### Masked bodies still contain raw HTML — Lane A (#108)

**11 of 15 stored messages** hold HTML markup in `messages.body_masked` — one is 5,933 characters
of `<!DOCTYPE html>`, CSS and `<div>` soup with the actual message buried inside it. Measured
2026-09-17 by inspecting every stored draft's source email while building the study instrument.

`#57` added HTML stripping to the listener before masking. Either these rows predate that fix or it
is not holding for multi-part messages.

Two consequences beyond the display problem. Markup inflates the text sent to the model, wasting a
256-token budget on style attributes; and PII inside HTML attributes is not necessarily reachable
by regex patterns written for prose.

Worked around in the study instrument by stripping at render (`build_study_instrument.py`), which
does nothing for what is stored or what the model receives.

**Update 2026-10-11:** #202 changed `collectParts` (`listener/bodies.go`) to join every body part
of a type rather than the first, and `getBody` (`listener/main.go`) prefers `text/plain` and runs
`htmlToText` otherwise. No stored-data re-measurement has been done since, and rows written before
these changes have not been rewritten, so this stays open until the stored rows are checked again.

### The category classifier is below its macro-F1 gate — Lane B
On the 120-email human-audited gold set (`backend/data/category/holdout_gold.csv`) the classifier
scores macro-F1 **0.8435**, below its 0.85 gate (`f1_gate_passed: false` in
`backend/results/category_metrics.json`). Security (F1 0.63) and client (F1 0.72) are the weak
classes. The latency gate passes (0.53 ms average on CPU).

### The priority classifier is at 70% accuracy against an 80% target — Lane B
The best configuration (RoBERTa-base, rubric-consistent labels) reaches 0.69 macro-F1 and 70%
accuracy on the 120-email human-labelled holdout (`AI_DOCS/priority-classifier.md`). The target in
`specs/features/priority-classifier.md` is at least 80% agreement with human labels.

### Sent replies can be lost while Presidio is down — Lane A
The listener stores a sent reply (`listener/sent.go`) only when its body and subject mask without
degrading; if Presidio is unreachable, or masking takes a fallback path, the row is not written and
the reply is not recorded for the waiting list. It is not retried later.

### The OCR "images sent" audit count can over-report — Lane A
The audit row's count of images sent for reading can be higher than the number Gemini actually
received, so it should be read as an upper bound.

### `sent_message.gmail_id` is unique across all mailboxes — Lanes A/B
`SentMessage.gmail_id` is declared `unique=True` on its own (`backend/app/db/models.py`), not
together with `user_id`. A Gmail message id is unique within one mailbox, not across mailboxes, so
two users sending through different mailboxes could in principle collide.

### SLA rules: three known gaps — Lane A
In `listener/sla.go`:
- Any body containing "to unsubscribe" forces LOW (`lowBodyRe`), even when the email also states a
  real deadline.
- The four-letter "Sept" abbreviation is not parsed as a month; "Sep" and "September" are.
- Day differences are cut at midnight UTC (`daysBetween`), not Malaysian time (UTC+8), so an email
  received between 00:00 and 08:00 local time can be a day off.

### Replies sent before #208 cannot be followed up — Lane B
Replies stored before #208 (fixed placeholder numbers for the owner and the sender) can contain a
placeholder that no longer resolves, so a follow-up cannot be drafted from them correctly. They
have not been repaired.

### The egress log misses listener OCR and the background embedding pass — Lanes A/B
`model_egress` records drafts, refines, translations, `/search`, `/ask` and, since 2026-10-12,
document indexing at upload. It has no rows for:
- the listener's attachment reading (OCR and checked scans), which runs in Go and has no writer
  for this table;
- the worker's background embedding pass (`embed_pending`), which batches chunks from any owner
  and only runs for retries and model changes.

### Training data for the priority classifier is not in git — Lane B
The category classifier's data, model and results are now tracked (`backend/data/category/`,
`backend/models/category-classifier.joblib`, `backend/results/category*`). The priority classifier's
labelled Enron sets and trained models are still gitignored (`backend/*.csv`, `backend/models/*`),
and so are the RAG policy PDFs and the local-model harness. What can be rebuilt, and what must be
obtained, is listed in [`data/reproducing-evaluations.md`](data/reproducing-evaluations.md).

## Known limitations, accepted deliberately

These are not defects — they are trade-offs with reasons, recorded so the reasoning is not lost.

- **Attachment redaction is only as good as the local OCR's view of the page.** The reader
  withholds a page the local OCR read with low confidence, but it cannot withhold text the OCR
  never detected at all: a line of handwriting beside confidently printed text would reach Gemini
  unredacted. The listener's `maskText` still runs on the transcript, which catches the formats it
  knows, but only after Gemini has seen the image. Accepted because the alternative, withholding
  any image with a region the OCR skipped, would withhold nearly every photo and logo. Since
  2026-10-10 this applies only to owners who chose checked scans; by default no scan image reaches
  Gemini (`specs/features/signature-detection.md`), and the local check also misses about 1 in 10
  signatures, faces and stamps.
- **Attachments are over-redacted where NER is unsure.** A capitalised label can be tagged as a
  name ("Bill to:" loses "Bill"). The business content that matters (amounts, dates, reference
  numbers) survives: `tests/test_reader.py` asserts it on a synthetic invoice.
- **Attachment text dropped during an NER outage is not recovered.** If Presidio is down when a
  message arrives, the whole message is quarantined and re-read later, attachments included. But
  if Presidio fails only while masking the attachment text (the body masked fine), that text is
  dropped and the message is stored without it: recorded as `drop_attachment_text` and counted on
  the admin console, not retried. Accepted because the body, which is what gets drafted from, is
  intact.
- **Only the first 20 pages of a PDF are read, within a 150 s budget**, and spreadsheet layout is
  flattened to one value per line. Pages left unread are reported in the audit row (`unread=`).
  Both bound the time and memory a single attachment can take.
- **Street numbers survive masking.** "12 Jalan Ampang" keeps the number. An address pattern would
  collide with dates, quantities and clause numbers, which the negative controls exist to prevent.
- **Organisation names are not masked.** Masking company names degrades draft quality, and the
  default NER model does not supply that entity type anyway.
- **A context-free account number is left visible.** The context gate is what stops every invoice
  and order number being redacted.
- **`from_addr` is stored unmasked.** `approve_and_send` needs a real recipient. It never enters
  the model payload.
- **Masking now blocks rather than degrades (changed 2026-09-29, #109).** If Presidio is
  unreachable, the message is quarantined with no content until it can be masked properly. The
  cost: a message arriving during an outage is not readable until Presidio recovers, and needs the
  listener running to be released.
- **A low-confidence draft is shown, not withheld.** Gating hard on an unvalidated self-reported
  score would silently discard work; the approval click is the real control.
- **Message content is kept until a limit is set.** `MESSAGE_CONTENT_RETENTION_DAYS` defaults to
  `0`, which keeps readable content (`backend/app/retention.py`), because clearing it removes the
  user's own inbox view. Every other retention policy expires by default.

## Housekeeping

- A stray `document` row titled "policy" with a single chunk is test residue in the RAG corpus.
- `models/distilbert-checkpoints/` is 1.4 GB of training artefacts; only `models/distilbert/` is
  used at runtime.
- Fourteen local branches exist, several from earlier team work that may never have merged.

## Fixed

### A follow-up whose Gmail outcome was unknown kept its claim — Lane B — FIXED 2026-10-12
It is now marked (`sent_message.follow_up_outcome_unknown_at`, migration 0043) and the reconciler
asks Gmail: sent, the claim stays; not sent, the claim is released so it can be sent again.

### Settings writes for a user without a profile row returned a generic 500 — Lane B — FIXED 2026-10-12
A user who signed in without granting Gmail had no `user_profile` row, which every settings table
points at. Every sign-in now creates the profile (`connections.remember_profile`). Someone who
signed in that way before the fix needs to sign in once more.

### Dismiss and "Not now" wrote no audit row — Lane B — FIXED 2026-10-12
`email_dismissed` (with `dismissed: true|false`) and `waiting_dismissed` are audited, like snoozing.

### The dataset generator could overwrite the human-audited gold set — Lane B — FIXED 2026-10-12
`generate_category_dataset.py` stops before any model call when `train.csv`, `holdout_gold.csv` or
`holdout_audit.csv` exists, unless run with `--force`. It also no longer loads `.env` when imported.

### Private mode did not cover unowned rows before the original owner connected — Lane B — FIXED 2026-10-12
The original `token.json` mailbox and its unowned rows were retired (`app/core/mailbox.py` removed);
every row has an owner, so every row follows its owner's Private mode setting.

### Names a person typed reached the model as typed — Lane B — FIXED 2026-10-12 (#215)
Refine instructions and drafts, Search, Ask AIMail, the inbox assistant, template translation and
earlier replies quoted as thread context masked only fixed formats. A new name now becomes a
`[PERSON_800+]` placeholder for one request (Presidio plus Malaysian name rules,
`backend/app/core/typed_names.py`, `backend/app/core/name_patterns.py`) and goes back into the answer.
Remaining limit: names in no recognisable form can still be missed by the English model.

### The privacy receipt dropped prompts from failed calls — Lanes B/C — FIXED 2026-10-12 (#215)
The agent returned egress records only on success, and the backend saved a draft's retrieval record
only after the agent answered. Refusals now carry `{"code", "egress"}` and every failure path saves
them; Search and Ask save in a `finally`.

### Past replies kept for style learning never expired — Lane B — FIXED 2026-10-12 (#215)
`document` rows of type `sent_reply` now expire after 365 days (`backend/app/retention.py`).
Style examples stay until the user removes them, because each one was chosen or pasted by the user.


### Page scrolls past the app into empty space — Lane D — FIXED 2026-09-29 (#96)

**Cause, measured:** each unread inbox row carried an `sr-only` "(unread)" label, and Tailwind's
`sr-only` is `position: absolute`. With no positioned ancestor inside the list's scroll container,
the label was placed against the page at its in-flow position (thousands of pixels down the list)
and escaped the `overflow` clipping. 21 unread labels stretched the document to 4211px on a 900px
viewport. It looked transient because it tracked which rows were unread, and container-level fixes
could not touch it. **Fix:** every scroll or clip container is `relative` (a unit test enforces
it), the app shell is `relative` as a backstop, and the label sits first in its row so it cannot
widen the list either. Verified in Chrome over CDP: document 900px, list width unchanged, a scroll
to y=99999 stays at 0. The investigation notes below are kept for the record.

The dashboard can be scrolled below the interface into blank space. An attempted fix (2026-09-04)
changed the shell from `h-screen` to `h-dvh` with `overflow-hidden` and set `html, body` to
`height: 100%` — **this did not resolve it**. Body overflow was deliberately not locked, since
`/extension` is a taller standalone page that must still scroll. Cosmetic, but visible in a demo.

**Measured 2026-09-15 (Lane B, handing to Lane D).** Three in-browser measurements:

| run | viewport | `html.scrollHeight` | verdict |
|-----|----------|---------------------|---------|
| 1   | 812      | 812                 | clean   |
| 2   | 812      | 3636                | **bug reproduced** |
| 3   | 731      | 731                 | clean   |

Run 3's viewport changed because devtools were docked, which forces a relayout. **The overflow is
transient: it survives until something invalidates layout, then clears.** That is why the container
fix looked like it failed and why the bug resists on-demand reproduction — measuring after a resize
destroys the evidence. In run 2 the document height (3636) tracked the inbox list's own content
height (3628, `InboxList.tsx:17`) to within 8px, but which element carries that height out to the
document root is **not** established.

Separately, and not the cause: `routes/index.tsx:117` (`aside`) and `:125` (`section`) sit between
`main.flex.min-h-0.flex-1` (`AppShell.tsx:20`) and both scroll containers, and carry neither
`h-full` nor `min-h-0`. They depend entirely on `align-items: stretch` for their height, which is
the fragile case when a child uses `h-full`. Worth tightening regardless.

Next step is to run this in the browser and then use the app normally — pop devtools into a
separate window first, because docking or resizing it clears the state being hunted. It stays quiet
until the overflow appears, then names the deepest element that no ancestor clips.

```js
(() => {
  const de = document.documentElement;
  let wasOverflowing = false;

  const clipper = (el) => {
    for (let n = el.parentElement; n; n = n.parentElement) {
      const o = getComputedStyle(n).overflowY;
      if (o === 'hidden' || o === 'auto' || o === 'scroll')
        return n.tagName + '.' + String(n.className || '').slice(0, 30);
    }
    return 'NONE';
  };

  window.__scrollWatch = setInterval(() => {
    const isOverflowing = de.scrollHeight > de.clientHeight + 4;
    if (isOverflowing === wasOverflowing) return;
    wasOverflowing = isOverflowing;
    if (!isOverflowing) return console.log('--- cleared');

    const shell = document.querySelector('.h-dvh');
    console.log('=== OVERFLOW', de.scrollHeight, 'vs', de.clientHeight,
      '| route', location.pathname,
      '| body children', document.body.children.length,
      '| h-dvh resolves to', shell ? getComputedStyle(shell).height : 'shell not found');

    [...document.querySelectorAll('*')]
      .map((el) => ({ el, bottom: Math.round(el.getBoundingClientRect().bottom + window.scrollY) }))
      .filter((o) => o.bottom > de.clientHeight + 4 && clipper(o.el) === 'NONE')
      .sort((a, b) => b.bottom - a.bottom)
      .slice(0, 8)
      .forEach(({ el, bottom }) => console.log('  ', bottom, el.tagName,
        String(el.className || '').slice(0, 45), '| pos', getComputedStyle(el).position));
  }, 250);

  console.log('watching. clearInterval(window.__scrollWatch) to stop.');
})()
```

### Uploaded documents are never masked — Lane B — FIXED 2026-10-04 for new uploads (#139)
`ingest_text` now masks every document before chunking (`app/rag/mask.py`): the fixed-format floor,
then Presidio for names, emails, phones, cards and IBANs. If Presidio is down the upload is refused
with `503 masking_unavailable`, never stored unmasked. Locations are kept on purpose. Documents
stored before the fix are tracked under Open.

### The refine instruction is unfenced user text — Lanes B/C — FIXED (#111)
`/refine` used to interpolate the user's free-text instruction straight into a prompt. Since #111
it goes inside a `user_instruction` fence (`fence('user_instruction', req.instruction)` in
`backend/email_agent.py`), with the rule that the tag carries a request about the draft, not a
change to the model's role.

### Generated drafts still contain a "Subject:" line — Lane C — FIXED (#204)
The generator wrote a subject line into the draft body; it was stripped only at send time
(`gmail_send.py`). Since #204, `assess()` in `backend/email_agent.py` runs `strip_subject_line`
(`backend/app/core/draft_text.py`) on every draft, generated, repaired or refined, before the
critic sees it and before it is returned as the stored draft.

### Masking silently degraded on a stored message — Lane A (#109) — FIXED 2026-09-29 (#116)

**Fixed:** the listener no longer stores degraded content. If NER is unavailable for any part of a
message, the row is quarantined (`masking_status = 'pending'`, no subject, body or snippet) and a
background loop re-fetches and masks it once Presidio's health check passes. The dashboard shows it
as awaiting masking and nothing drafts from it. Rows stored degraded *before* the fix are still
found only by `backend/scripts/remask_outliers.py`. The original finding follows.

`body_masked` for one message left a real person's name and town in plain text. Found 2026-09-17
while selecting drafts for the study.

The evidence is stronger than usual because it is a controlled comparison. Five near-identical
copies of the same support email exist in the corpus. Four carry 12, 12, 9 and 12 redactions; the
fifth carried 6, with the name and location unredacted. **Same input, masked correctly four times
and incorrectly once.**

The likely cause is documented below as accepted behaviour: masking degrades to regex-only when
Presidio is unreachable, and NER is what catches names and places. What was not known is that this
had actually happened to stored data rather than remaining a theoretical fallback.

The row was repaired with `backend/scripts/remask_outliers.py`, which finds candidates by the same
redaction-count comparison, re-runs Presidio, and rewrites the stored body. That repairs data; it
does not stop it recurring.

**This matters for how the masking evidence is reported.** The fixture passes 38/38, but it was
written after the implementation, so it demonstrates that no *known* failure mode is unhandled.
This is an unknown one, and it was found by accident. The honest claim is narrower than "masking
works".

Worth doing: have the listener record the degraded path per message rather than only in the audit
log, so a degraded row is identifiable without comparing it to its siblings.

### The Gmail watch never renewed — Lane A — FIXED (#113)
Gmail expires a `users.watch` after about seven days, and nothing renewed it, so notifications
stopped silently. Since #113 the listener renews on `watchRenewInterval`, inside Gmail's expiry (a
test in `listener/main_test.go` enforces that), and audits each renewal as `renew_watch`.

### Ingestion fetched "the latest message", not what changed — Lane A — FIXED (#113)
The listener used to fetch the newest message on each notification rather than what the
notification reported as changed. Since #113 it reads the Gmail history (`History.List`).
