# Restorable masking: the AI never sees personal details, your reply still says "Hi Aisyah"

- **Status:** built and checked live 2026-10-05: a real email's vault opened, no stored or
  AI-written text held a real detail, and the approved reply went out with 3 details filled in
  while the stored copy kept placeholders. Cross-lane, see "Lanes"
- **Owner:** veyroxie; Lane A (JiaJun) for the listener part, Lane C (Hanif) for the prompts,
  Lane D (Han) for the dashboard
- **Related:** [ADR 0006](../../docs/adr/0006-restorable-masking.md),
  [per-user-mailboxes.md](./per-user-mailboxes.md), [writing-profile.md](./writing-profile.md),
  gap-plan epic #138
- **Last updated:** 2026-10-05

## Problem

Masking replaces every personal detail with a fixed marker (`[Redacted]`, `[PHONE_REDACTED]`)
before anything is stored. That keeps details away from the AI, but also from the person replying:
in the 5 Oct test the reader could not tell the sender was "Aisyah", the draft said "Hi [Name]",
and every reply needed the original opened in Gmail to fill details back in by hand. A marker the
reader forgets reaches the customer as written.

## Goal

The AI still never sees a personal detail. The mailbox owner sees the real email and a draft with
the real details in it, and the sent reply carries them. Nothing readable is stored: the details
are kept only encrypted, with a key that is not in the database.

## User story

As a support agent, I open an email from a customer, see her name, IC and phone as she wrote them
(marked as "hidden from the AI"), get a draft that greets her by name, and send it without
retyping anything, knowing the AI only ever saw `[PERSON_1]`.

## Scope

**In scope**
- Numbered, typed placeholders instead of fixed markers, consistent within a message and a thread.
- A per-message encrypted "vault" mapping each placeholder to its real value.
- Showing the owner the real details in the email, the thread and the draft, with a hide toggle.
- Turning real details back into placeholders before anything goes to the AI (refine, follow-up
  context), and placeholders back into real details when sending.
- A send check for placeholders that have no value, and a warning for template placeholders the
  model invents (`[Your Name]`).
- Signing replies with the owner's name from their Google account.

**Out of scope**
- Re-masking emails stored before this ships (they keep fixed markers; optional script later).
- Restoring details hidden inside images: the OCR redactor blacks them out (`[REDACTED]`), and
  that stays unrestorable.
- Documents in the knowledge base: they stay masked the old way (nobody replies to a document).

## How it works

```
 Gmail ──► listener: mask with numbered placeholders ──► messages.body_masked  "Hi, I'm [PERSON_1]"
                     └─ vault {PERSON_1: "Aisyah"} ─────► messages.pii_vault   (AES-256-GCM, sealed)

 backend: thread map (all vaults in the thread, one number per person)
   ├─► AI:        masked text only; typed text re-tokenised first      "Hi [PERSON_1], ..."
   ├─► dashboard: masked text + the owner's details to display         "Hi Aisyah, ..." (highlighted)
   └─► Gmail:     approved reply, placeholders restored at send time    "Hi Aisyah, ..."
```

1. **Numbered placeholders (listener).** Every detail becomes `[KIND_N]`: `PERSON`, `EMAIL`,
   `PHONE`, `IC`, `PASSPORT`, `ACCOUNT`, `CARD`, `LOCATION`, `ORG`. The same value gets the same
   number everywhere in the message (subject, snippet, body, attachment text), compared after
   normalising (case and spacing for names, digits only for numbers). One numbering state is
   carried across the NER chunks and fields of a message, so a name split across chunks still
   gets one number.
2. **Replacement in Go, not the anonymizer.** The analyzer already returns each entity's span; the
   listener replaces spans itself (by rune offset, longest first, overlaps merged), so it knows
   every value it hides. The anonymizer container is no longer needed for masking; the health
   check is updated to match.
3. **The vault.** `{placeholder: value}` as JSON, sealed with AES-256-GCM under `PII_VAULT_KEY`,
   with the owner and Gmail message id as associated data (a vault copied to another row does not
   open). Stored in the new `messages.pii_vault BYTEA NULL` column, written in the same insert as
   the masked row (and by the quarantine release). A row whose masking degraded stores no vault and
   no content, as today.
4. **Thread map (backend).** For a message and its thread (same owner), the backend opens each
   vault and assigns thread-level numbers in order of first appearance: the same person is
   `[PERSON_1]` in every message of the conversation. Numbers only grow, so a stored draft stays
   valid when new messages arrive. Message text is renumbered into thread space before it is shown
   or sent to the AI.
5. **Showing the owner.** Detail responses add `details: [{placeholder, value, kind}]` for the
   email, its thread and its draft. The dashboard substitutes them for display and highlights each
   one ("hidden from the AI"). A **Hide details** toggle (remembered per browser) shows the
   placeholders instead, for screen sharing and demos. The draft editor shows real values.
6. **Back into placeholders before the AI.** Anything the owner typed or edited (refine draft and
   instruction, a sent reply used as follow-up context) goes through `retokenise`: every known value
   in the thread map becomes its placeholder (longest first, whole words, names case-insensitive),
   then the existing typed-text masking catches new formatted details. `draft_reply` is always
   stored in placeholder form, including the approved text after a send, so the database never
   holds a readable detail outside a vault.
7. **Restored at send.** The backend re-tokenises the approved text, then restores every placeholder
   from the thread map, and sends that. A placeholder with no value (the model invented
   `[PERSON_7]`, or the vault cannot be opened) refuses the send with
   `422 unresolved_placeholders`. Fixed markers (`[Redacted]`) keep today's
   `422 redaction_markers`.
8. **Template placeholders.** The generator is told to copy placeholders exactly, never to write
   its own bracket placeholders, and to sign off with the owner's name when given. The dashboard
   warns before sending a draft containing any other `[Bracketed Text]`, with "Send anyway", like
   the existing marker warning.
9. **The vault expires.** A daily job empties `pii_vault` once a message is older than
   `VAULT_RETENTION_DAYS` (default 30), or 7 days after its reply was sent, whichever is first. The
   details are kept only while a reply may still be written. After that the email shows its
   placeholders with a note, and the original is read where it lives: in Gmail, through the Chrome
   extension (see "Seeing the original").
10. **Signature.** At sign-in, the owner's name from their Google account (Supabase
   `user_metadata.full_name`) fills `user_profile.display_name` if empty; the generator receives it
   as the sign-off name.

## Seeing the original

The owner decided (2026-10-05) that the original email is read in Gmail itself, through the Chrome
extension panel beside it, rather than an "Open in Gmail" link or a second copy rendered inside
AIMail. The extension is a separate feature (Lane D); this spec only guarantees the panel can show
the same `details` the dashboard does.

## As built (2026-10-05)

- The dashboard shows each detail highlighted ("hidden from the AI") in the subject, body (plain and
  HTML, inserted after sanitising and only as text), summary, action items, thread and translation,
  and the draft editor holds the real values. **Hide details** sits in the email header and the
  panel header, one switch for the whole page, remembered per browser.
- A draft still holding bracketed template text (`[Your Name]`) asks before sending, like the marker
  warning; `unresolved_placeholders` explains itself in three languages.
- Placeholders with no value (expired or unopenable vault) show a notice pointing to Gmail.
- The listener numbers Presidio entities in reading order; live recall stays 44 of 44.

## Data model (migration 0018; `specs/context/db-schema.md` first)

| Column | Type | Notes |
|---|---|---|
| `messages.pii_vault` | `BYTEA NULL` | emptied by the retention job (see "The vault expires"); version byte, 12-byte nonce, AES-256-GCM ciphertext of the JSON map; AAD `aimail-pii-vault:v1:<user_id or "">:<gmail_message_id>`. NULL for rows from before this, quarantined rows, and degraded masking |

No other schema change: the vault lives and dies with its row, so disconnect and account deletion
remove it with the mail.

## API changes (`specs/context/api-contracts.md` first)

- *Built 2026-10-05, backend and agent:* the shared pattern was split rather than widened.
  `REDACTION_MARKER` still means only the unfillable markers (the critic's leak check and the send
  check use it), `PLACEHOLDER` is the numbered form, and `ANY_MASK` (both) is what a translation must
  preserve. Otherwise every draft holding `[PERSON_1]` would have been flagged as a leak. The owner's
  sign-off name is itself a thread placeholder, so the AI never receives it. `Cache-Control:
  no-store` was already on every API response.
- `DashboardEmail.details: {placeholder: string, value: string, kind: string}[]` on detail,
  regenerate, refine and send responses (empty on the list endpoint and for old rows). Only ever
  the signed-in owner's own details (the scope already guarantees it).
- Detail responses carry `Cache-Control: no-store`.
- `POST /emails/{id}/send`: new `422 unresolved_placeholders`.
- Lane C payloads are unchanged in shape; they carry `[KIND_N]` placeholders instead of fixed
  markers. `REDACTION_MARKER` (shared by the agent, the send path and the dashboard) also matches
  `[KIND_N]`, so the critic's placeholder check and the translation faithfulness check keep working.

## Security & privacy

- **The AI's view is unchanged in substance:** placeholders, never values. Numbering reveals only
  "the same person appears twice", which the old markers hid; accepted as needed for a coherent
  reply.
- **New stored data:** personal details, encrypted. Readable only with `PII_VAULT_KEY`, which lives
  in `.env` beside `TOKEN_ENCRYPTION_KEY`, never in the database. A database leak alone reveals
  nothing; a database leak plus the key reveals details already less sensitive than the Gmail
  tokens those same keys protect.
- **Separate key from the token key**, so either can be rotated or revoked alone.
- Values are decrypted only in backend memory for one request, never logged, never in audit rows,
  never in the admin console, never sent to the agent. Audit rows record counts ("restored 3").
- **PDPA:** collected for one purpose (showing the owner and completing their reply), deleted with
  the mail on disconnect or account deletion.
- **The landing page claim changes** from "hidden before any AI sees them" (still true) to also say
  details are stored only encrypted.
- **Human review stays the last check:** if the model uses the wrong placeholder, the owner sees the
  wrong real name in the draft before sending, which the old markers could never show.

## Failure modes

| Situation | Behaviour |
|---|---|
| Row from before this ships | Fixed markers as today; send check unchanged |
| Vault missing or cannot be opened | Masked view with a notice; placeholders left in the draft block the send with `unresolved_placeholders` ("type the details yourself") |
| `PII_VAULT_KEY` unset in the listener | Masking still runs; no vault stored; a startup warning |
| `PII_VAULT_KEY` unset in the backend | Masked view everywhere; sends with placeholders refused |
| Vault expired | Placeholders with a note; the original is in Gmail; a draft still holding placeholders cannot be sent until they are typed in |
| Presidio down | Quarantine as today; no content, no vault |
| Model invents `[PERSON_9]` | Send refused until the owner fixes it |
| Model writes `[Your Name]` | Dashboard warning, "Send anyway" possible |

## Lanes and rollout

| Lane | Change |
|---|---|
| A, listener (JiaJun) | numbered placeholders, span replacement in Go, vault sealing (`PII_VAULT_KEY`), shared test vector |
| B, backend (veyroxie) | migration 0018, vault opening, thread map, `retokenise` / `restore`, `details` field, send check, sign-off name |
| C, agent (Hanif) | prompt rules (copy placeholders, no invented brackets, sign-off name), `REDACTION_MARKER` pattern |
| D, dashboard (Han) | substitution and highlight, Hide details toggle, template-placeholder warning, `unresolved_placeholders` message (three languages) |

Order: backend and agent first (they accept both marker styles), then the listener, then the
dashboard. Each step is mergeable alone.

## Acceptance criteria

- [ ] A new email's stored text holds only `[KIND_N]` placeholders; the same person has one number
      across subject, body, attachment text and the whole thread.
- [ ] No request to the agent or Gemini contains a vault value (asserted on captured payloads,
      including refine and follow-up context after a send).
- [ ] The owner sees the real details in the email, thread and draft, each highlighted; Hide details
      shows placeholders; another user sees nothing (404, as today).
- [ ] A draft with `[PERSON_1]` is sent as "Aisyah"; the stored `draft_reply` keeps `[PERSON_1]`.
- [ ] Editing the draft to include the real name and refining it sends the AI `[PERSON_1]`.
- [ ] An invented placeholder or an unopenable vault refuses the send; old rows behave as today.
- [ ] No log line, audit row or admin response contains a vault value (grep after a full run).
- [ ] The vault does not open under another row's id or another user's id (tests in Go and Python
      on one shared vector).
- [ ] The draft signs off with the owner's Google name instead of `[Your Name]`.

## Test plan

- Go: numbering consistency (repeats, case, chunk boundaries, overlapping spans), vault round trip,
  wrong-AAD refusal, shared vector with Python.
- Python: thread map renumbering and stability, `retokenise` (longest first, whole words, case),
  `restore`, send refusals, captured agent payloads contain no values, `details` only for the owner.
- Dashboard: substitution and highlight, toggle, warning, error text.
- Live: the 5 Oct test email again, end to end, with the payload log checked for the name, IC and
  phone.

## Decisions (2026-10-05, the owner accepted every recommendation)

The questions below were answered "yes to all", plus the expiry and "see the original in Gmail
via the extension".

## Open questions (as asked; recommendation first)

1. **Where the real details come from at send time.** *Recommended:* the stored, encrypted vault.
   *Alternative:* store nothing, re-read the original from Gmail and re-mask it at send time; no
   new stored data, but sending would need Presidio up, would break if the original was deleted, and
   breaks silently if Presidio ever splits a name differently the second time.
2. **Default view.** *Recommended:* real details shown, highlighted, with Hide details. *Alternative:*
   hidden by default with a reveal click.
3. **Key.** *Recommended:* a new `PII_VAULT_KEY`. *Alternative:* reuse `TOKEN_ENCRYPTION_KEY` with
   a different associated-data prefix (one fewer setting, but one key to rotate for two purposes).
4. **Old emails.** *Recommended:* leave them; offer a re-mask script later. *Alternative:* re-mask the
   43 stored emails from Gmail now.
5. **Sign-off name.** *Recommended:* from the Google account at sign-in, editable later by the
   writing profile. *Alternative:* wait for the writing-profile feature.

## Estimate

About three days: listener one, backend one, agent and dashboard one, plus the live check.
