# ADR 0003 — Mail is ingested server-side only; a Gmail side panel may show it, read-only

- **Status:** Proposed
- **Date:** 2026-10-08
- **Deciders:** veyroxie (proposer); Lane A and D owners to confirm
- **Supersedes:** [ADR 0001](0001-no-chrome-extension.md) once accepted

## Context

ADR 0001 ruled out a Chrome extension because one would scrape Gmail's page and handle mail before it
was masked, and named n8n as the ingestion path. Two things changed. n8n was retired: the Go listener
receives Gmail's Pub/Sub notifications, pulls the message with the Gmail API and masks it before
anything is stored (`specs/architecture.md`). And a side panel was built
(`specs/features/chrome-extension.md`) that reads only the open thread's id from Gmail's page and
shows the backend's masked copy, summary and draft beside it.

## Decision

Mail enters AIMail only through the listener and the Gmail API, masked before storage. A browser
extension may show what the backend already holds, keyed by the open thread's id, and must never read
message content from the page or send it anywhere.

## Rationale

- ADR 0001's real objection, unmasked mail handled in the browser, does not apply to a panel that
  reads an id and asks the backend, which only ever returns the masked copy.
- One ingestion path keeps masking in one place, which is what the privacy claims rest on.
- The panel answers the usability gap (switching between Gmail and the dashboard) without a second
  source of mail.

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Keep ADR 0001 as written | It forbids a panel that does not do what 0001 feared, and still names n8n. |
| Let the extension read the open email's text | A second, unmasked ingestion path in the browser: exactly ADR 0001's objection. |

## Consequences

**Positive:** the panel is allowed and bounded; ingestion and masking stay in the listener.

**Negative:** the panel depends on Gmail's page exposing the thread id, which can change without
notice; when it breaks, the panel shows nothing rather than anything wrong.

## Revisit conditions

- The panel needs any content from the page beyond the thread id.
- A mail provider is added that has no server-side API.
