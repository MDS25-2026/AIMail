# Readable emails, attachments on the hosted app, and nothing sent without a click

- **Status:** built 2026-10-12 (reprocessing stored emails waits for the owner's yes after the dry run:
  245 would change, 99 of them with an unsent draft that would be drafted again; 12 replied-to skipped)
- **Owner:** veyroxie
- **Related issue:** #224 (items W, X and Y)
- **Last updated:** 2026-10-12

## Goal

Emails from Gmail and Outlook often read badly in AIMail: ragged lines, big empty gaps, tables
run together, bullets lost, whole reply chains shown, links as raw text. The cause is the
listener's regex HTML stripper and its preference for the mail client's auto-made plain text.
Separately, attachments are never read on the hosted app because the reader was not deployed,
and nothing on the email says so. And Settings should say plainly that nothing sends without a
click.

## User stories

- As a mailbox owner, I want an email to read the way its sender laid it out, so that I can
  take it in at a glance.
- As a mailbox owner, I want earlier messages folded away, so that I see what's new first.
- As a mailbox owner, I want to know when a PDF couldn't be read, so that I open it myself.

## Scope

**In scope**

- **A real HTML-to-text converter in the listener** (Go's `golang.org/x/net/html`, already in
  the module graph; the owner approved making it direct). It runs where the original HTML still
  exists, before masking. It is not part of the normaliser, which only sees masked text and
  handles numbers, units and dates.
  - Paragraphs, headings, `div`s and line breaks become line breaks; runs of spaces, tabs,
    newlines and non-breaking spaces inside text collapse to one space; lines that hold only
    whitespace are dropped; three or more line breaks become two.
  - Lists keep bullets ("- ") and numbers ("1. ").
  - A table row whose cells are all short and single-line reads as `a | b | c`; any other row
    (layout tables in newsletters) puts each cell on its own line.
  - `blockquote` lines start with "> ", so the dashboard can fold them.
  - Links read "text (url)", or just the URL when the text is the URL; `mailto:` links keep
    their text only (the address is masked anyway). Kept as text because the agent's phishing
    check reads where a link points.
  - Dropped: `script`, `style`, `head`, `title`, comments (which hold Outlook's
    `<!--[if mso]>` blocks), images.
  - `<pre>` keeps its spacing.
- **The HTML part is preferred over text/plain** when a message has both. Gmail's plain text is
  hard-wrapped at 76 characters and Outlook's turns bold into `*text*` and links into `<url>`.
  text/plain is used only when there is no HTML; then `format=flowed` soft breaks are joined.
- **Folded reply chains in the email view:** the body is split at the first line that starts a
  quoted email ("> ", "-----Original Message", "From: ", "On ... wrote:", "Pada ... menulis:",
  "...写道:", including the two-line "On ..." / "wrote:" form). Only the new part shows; "Show
  quoted text" reveals the rest. The patterns match `listener/sla.go` and `backend/app/waiting.py`.
- **Clickable links** in the email body: `http(s)` URLs open in a new tab
  (`rel="noopener noreferrer"`). The URL itself stays visible as text.
- **The email view's top bar stays put:** one row (back, read/unread, snooze, privacy receipt,
  details, priority, and the subject cut to one line, in full on hover) stays at the top while the body
  scrolls; the sender, date and notices scroll with the body. Its bottom border marks the edge.
- **Replies sent from Gmail itself appear in the conversation** as "You", where they fall in time
  (they were only used for the To-do). Their hidden details have no stored values, so they take new
  placeholder numbers with none: shown hidden, never as another person's name.
- **Reprocess stored emails:** a listener command fetches each stored email from Gmail again,
  extracts it the new way, masks it again and saves the body, preview, subject, counts and vault.
  Masking again renumbers the hidden details, so the email's summary, action items, draft and
  critic result are cleared and the worker drafts them again. Skipped: emails replied to or sent,
  past retention (body already cleared), quarantined, or whose Gmail message no longer exists.
  `--dry-run` (the default) counts and prints only ids and counts; writing needs `--write` and the
  owner's yes.
- **The attachment reader on the hosted app:** `aimail-attachment-reader`, a private Render
  service (Standard, about 2 GB), and the listener's `ATTACHMENT_READER_URL` set to its internal
  address plus `/read`.
- **A note on the email when an attachment couldn't be read:** "An attachment couldn't be read, so
  AIMail hasn't seen what's in it", with Open in Gmail. Found from the listener's failed
  `read_attachment` / `ocr_attachment` audit rows for that Gmail message, excluding text dropped on
  purpose. A yes/no, not a count: a retried read writes another row.
- **Settings:** the holding-reply card says "AIMail never sends anything without your click. This
  is the one exception, and it's off unless you switch it on." (The landing FAQ already says so.)

**Out of scope**

- Storing or showing the original HTML (colours, fonts, images): names would sit inside markup,
  which is what lowered Presidio's recall before (`getBody`'s comment).
- Calendar invites (`text/calendar`), Outlook's `winmail.dat`, inline `cid:` images.

## Acceptance criteria

- [ ] Given an Outlook email with `<p class=MsoNormal>&nbsp;</p>` spacers, a conditional comment
      and an `<o:p>`, then the text has no blank-looking lines, no comment content, and paragraphs
      separated by one blank line.
- [ ] Given a Gmail email with both parts, then the HTML part is used and lines are not wrapped at
      76 characters.
- [ ] Given `<ul><li>One</li><li>Two</li></ul>`, then "- One" and "- Two" on their own lines.
- [ ] Given a two-column invoice table, then each row reads "Item | Amount".
- [ ] Given a newsletter laid out in nested tables, then no "|" appears and each block is on its
      own line.
- [ ] Given `<a href="https://x.com">https://x.com</a>`, then the URL appears once.
- [ ] Given a reply with "On Mon, 6 Oct 2026 at 10:00, [PERSON_1] <[EMAIL_1]> wrote:" and the old
      message below, then the view shows only the new part and a "Show quoted text" button.
- [ ] Given a body with a URL, then it is a link that opens in a new tab.
- [ ] Given a long email, when the reader scrolls, then the top bar stays visible.
- [ ] Given an email whose PDF failed to read, then the email shows the note; given one withheld on
      purpose, it does not.
- [ ] Given `reprocess` without `--write`, then nothing is written and it prints how many emails it
      would change and why others are skipped.
- [ ] Every new string exists in English, Malay and Chinese.

## API surface

- `DashboardEmail` gains `hasUnreadAttachment: bool` (false when none). Additive.
- `threadContext` also holds the owner's replies sent from Gmail itself (`isOwnReply: true`).

## Data model

None. The reprocess command updates existing `messages` columns only.

## Edge cases & failure modes

- **HTML that fails to parse:** `x/net/html` never fails on bad markup; it repairs it, as browsers
  do.
- **A message with only an image:** empty body, as today.
- **Quote markers inside the sender's own text** (a line starting "From: " in a signature block):
  the rest folds behind "Show quoted text", never lost.
- **Reprocess while the listener runs:** the command claims nothing the listener writes; a message
  that arrives during the run is new and untouched.
- **Reprocess with Presidio down:** the email is skipped, never stored half-masked.

## Security & privacy notes

- Masking still runs on clean prose, so recall is unchanged or better (no markup next to names).
- The reprocess command prints ids and counts only, never content.
- Links are only `http(s)`; nothing else becomes clickable.

## Decisions

- 2026-10-12: Prefer converted HTML over text/plain. Was text/plain first because markup next to
  names lowered Presidio's recall; a parser that outputs prose removes that reason.
- 2026-10-12: Fold quotes in the dashboard, not in storage, so nothing the sender wrote is lost and
  the SLA and waiting checks keep reading the full body as before.
