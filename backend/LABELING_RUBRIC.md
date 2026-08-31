# Email priority labeling rubric (enron_train_human.csv)

Provenance: rows 0-34 hand-labeled by Elyesa (interactive labeler, 2026-08-21).
Rows 35-958 labeled by Claude (Opus 4.5) in the same session, calibrated on those
35 examples plus ~10 live judgments Elyesa reviewed one-by-one before delegating.
Labels were assigned from the first ~1,200 characters of each email (the
interactive tool shows 2,500). The 120-row holdout (holdout_to_label.csv) is
fully human-labeled and was NOT touched.

## Tiers

**high** — needs action / high-stakes / authority directive.
- A named person awaits the recipient's response or action: direct questions,
  review requests ("please take a look and confirm"), approvals, chases
  ("have you had a chance to look at this yet?"), scheduling asks aimed at you.
- Whole-message tasks, however small: "please print", "add me to the list",
  "rebook this deal", "map this curve".
- Authority or employment/money directives: division sold, bankruptcy-era
  reporting-to-work memos, legal hold ("do not delete"), pay-change
  instructions, benefits forms with a pay-impacting deadline.
- Live counterparty/deal negotiations where the ball is in the recipient's court.
- Workflow approvals blocking a named colleague (access-request approvals).

**medium** — work-relevant, nothing owed by the recipient.
- FYIs, status updates, deliverables arriving ("attached is the report"),
  answers that close a loop ("done.", "deal created").
- Meeting notices, reminders, RSVP forms, event/travel logistics.
- Market, regulatory, and operational intel: pipeline notices, ISO warnings
  (in a mailbox that consumes rather than acts on them), intel reports,
  single news stories on the recipient's active matter.
- Org announcements, policy changes with substance, broadcast logistics with
  real dates (office moves).
- Trivial relay asks appended to info ("please forward to your groups").

**low** — automated, bulk, or social.
- Automated system output: CAISO scheduler logs, request-closed notices,
  calendar artifacts, expense-status emails.
- Bulk blasts: IT templates, mass surveys, exchange/association notices,
  daily news digests, newsletters, vendor ads, spam.
- Personal/social: fantasy football, family threads, banter, joke forwards,
  congrats/thanks notes, one-line acks.
- Recurring conveyor-belt data feeds (daily noms/actuals attachments).

## Edge rules applied consistently

- Bulk with a nominal action (mass survey) -> low; personally-addressed request
  awaiting response -> high. "Needs action" means someone waits on YOU.
- Labels are per-recipient: a CAISO bid solicitation in a gas trader's mailbox
  is medium (market color), in a power scheduler's it would be high.
- Personal-sphere or school pending asks -> medium; pure chat -> low.
- News: multi-story digests -> low; single deliberately-shared story on the
  recipient's active matter -> medium.
- Replies that close a loop -> medium even when one line ("done.").

## Comparison with Gemini labels (enron_gemini_labels.csv)

Agreement 459/959 (47.9%). Gemini runs hot: 315 high vs 177 here. Largest
disagreement buckets: gemini-high -> medium (139), gemini-medium -> low (140).
Gemini tends to rate FYIs, newsletters, and org announcements as high.
