# Privacy gaps found by the documentation pass

- **Status:** built 2026-10-12 (PR #215); backups waiting on the owner
- **Epic:** #138 line 95 (PDPA)

Writing the privacy notice (`docs/privacy/privacy-notice.md`) turned up places where AIMail keeps or
sends more than it says. The owner agreed to close them in the same PR.

## 1. Names a person types are hidden from the model

**Before:** typed text (a Refine instruction and the draft it edits, Search, Ask AIMail, the inbox
assistant, a template being translated, and earlier sent replies quoted as thread context) had only
fixed formats masked (`app/core/typed_text.py`). A name typed on purpose reached Gemini as typed.

**After:**
- Known details still become their thread placeholders (`ThreadMap.tokenise_known`), and fixed
  formats are still masked by `mask_typed_text`, which stays the floor shared with the listener.
- Presidio then finds any remaining PERSON in the typed text, and rules add the Malaysian name forms
  its English model misses (`app/core/name_patterns.py`): Malay patronymics (bin, binti, binte, bt,
  bte), Indian (a/l, a/p, anak lelaki, anak perempuan, s/o, d/o, and initials such as "R. Kumar"),
  Iban and Bidayuh (anak, ak), hereditary prefixes that are part of the name (Tengku, Tunku, Raja,
  Syed, Sharifah, Wan, Nik, Megat), common Malay given-name leads (Muhammad, Mohd, Siti, Nur, Abdul),
  Chinese surnames written first ("Tan Mei Ling"), the name after a title (Encik, Puan, Dato',
  Datuk, Tan Sri, Puan Sri, Tun, Haji, Dr), and Chinese characters before a form of address
  (陈先生, 王经理). Over-matching only hides a word the answer gets back; under-matching sends a
  name, so the rules lean wide. Titles stay visible. Each
  new name gets a placeholder from `[PERSON_800]` up, which no thread uses (thread numbers start at
  1; the owner and the sender are 900 and 901). The same name gets the same number within a request.
- The map lives for one request only. The names go back into what the model returns (the draft, the
  review reasons, the answer) before anything is stored or shown. Nothing new is stored, and the
  send path is unchanged: a refined draft holds the typed name, as it did before.
- Only PERSON is detected. Locations and organisations in instructions ("send it to the Maybank
  branch") are what the user means and are not personal.
- If Presidio cannot be reached, the request is refused with `masking_unavailable` (fail closed, as
  for documents), rather than sending the name.
- The inbox assistant matches senders by name in the local database. That match still uses the
  typed name, which never leaves the machine; the model sees the placeholder.

**Limit:** a name in none of these forms, typed alone ("ask Aisyah"), relies on the English model
and can be missed. The privacy notice says so.

## 2. The privacy receipt records prompts from failed calls

**Before:** the agent returned its egress records only when a call succeeded, and the backend saved
the retrieval record of a draft only after the agent answered. A prompt that reached the model
before a timeout or a refusal was missing from the receipt.

**After:**
- The agent's error answers carry `detail: {"code": ..., "egress": [...]}`. The backend saves those
  records on every failure path (draft, refine, translate, template translation). Only this dict
  shape is trusted; FastAPI's own validation errors (a list) carry no records.
- The backend saves records it collected itself (retrieval, Search, Ask) in a `finally`, so a later
  failure no longer drops them.

## 3. Learning data expires

**Before:** a reply kept for "Learn from the replies I send" (a `document` row of type
`sent_reply`) and a style example taken from a send (`style_example.source = 'sent'`) were kept
until the user disconnected Gmail or deleted the account.

**After:** past replies are deleted 365 days after they were stored, by the existing daily
retention job (`app/retention.py`, policy `past_replies`), sooner when a message content limit is
set. Deleting a document deletes its chunks and vectors (`ON DELETE CASCADE`, migration 0001). On
2026-10-12 the shared database held no past replies, so the first run deletes nothing.

Style examples are not expired. Building this showed that `source = 'sent'` examples are not
collected automatically: the user picks each one in Settings (`writing_style_routes.add_example`),
up to a small cap, like a pasted one. Deleting them on a timer would undo the user's own choice.

## 4. Older audit records checked for personal details

A read-only scan (`scripts/scan_audit_details.py`) counts audit rows from before the structured
format (2026-10-08) whose detail text looks like an email address, phone number or IC number. It
prints counts and row ids only, never the matched text. The log is append-only, so any finding is
reported to the owner rather than edited.

**Result 2026-10-12:** five free-text rows matched the card pattern, all `setup_watch` rows whose
13-digit number follows the word "expiration": Gmail's watch expiry in milliseconds, not a card.
Nothing matched an email address, phone, IC or passport number.

## Not in this change

- **Backups** were added 2026-10-12 in a follow-up: `make backup` runs `pg_dump` 17 from a pinned
  `postgres:17` image (the installed client is 16, which refuses a newer server) and keeps the
  newest 7 dumps outside the repo.
- **Email content retention** stays off until hosting (`MESSAGE_CONTENT_RETENTION_DAYS`).
