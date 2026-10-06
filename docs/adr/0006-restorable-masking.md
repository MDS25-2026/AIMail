# ADR 0006 — Restorable masking: numbered placeholders with an encrypted per-message vault

- **Status:** Accepted by the owner 2026-10-05 (Lane A, C, D owners to be told)
- **Date opened:** 2026-10-05
- **Deciders:** veyroxie (proposer); Lane A, C and D owners to confirm
- **Extends:** the listener masking design (CLAUDE.md "masks PII here"); ADR 0005 stage 2

## Context

Masking replaces personal details with fixed markers before storage, so the AI never sees them. It
also hides them from the person replying, who cannot greet a customer by name or answer about "her
IC" without opening Gmail, and a forgotten marker reaches the customer as "[Redacted]". The owner
asked for replies that carry the real details while the AI still sees none (5 Oct test).

## Decision

**Mask with numbered, typed placeholders (`[PERSON_1]`) and keep each message's placeholder-to-value
map in an encrypted vault on its row.** The AI only ever receives placeholders; the backend opens the
vault to show the owner their own details and to restore them in an approved reply at send time.
Anything typed by the owner is turned back into placeholders before it reaches the AI. Full design:
`specs/features/restorable-masking.md`.

## Rationale

- **The AI's view does not change in substance:** values never leave the machine for a model.
- **Established primitives only:** AES-256-GCM from the standard libraries already used for Gmail
  tokens (`token_crypt.py`, `tokencrypt.go`), with the row identity as associated data.
- **Human review gets better, not weaker:** the owner reviews the reply as the customer will read
  it, including any placeholder the model used wrongly.

## Alternatives considered

- **Re-derive the details from Gmail at send time** (no stored values). Rejected as the default:
  sending would depend on Presidio, on the original still existing, and on masking producing the
  same spans twice, and a mismatch would put the wrong detail in a reply without any error.
- **Keep fixed markers and add an "Open in Gmail" link.** Solves "who is this?" but leaves every
  reply to be completed by hand, which is the cost being removed.
- **Send real details to the AI.** Rejected: it is the product's central promise.

## Consequences

- New stored data: personal details, encrypted, readable only with `PII_VAULT_KEY` (not in the
  database). Kept at most 30 days, or 7 days after the reply (`VAULT_RETENTION_DAYS`), and deleted
  with the mail.
- New setting `PII_VAULT_KEY` for the listener and backend.
- The Presidio anonymizer is no longer needed for masking; replacement moves into the listener.
- `REDACTION_MARKER` gains the `[KIND_N]` shape in the agent, backend and dashboard.
- The landing page's privacy text adds "stored only encrypted".

## Revisit when

- Enterprise accounts share mailboxes (who may open whose vault).
- A local model replaces Gemini (specs/features/local-model.md): masking stays, but the threat
  model for the AI's view changes.
