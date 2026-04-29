# ADR 0001 — No Chrome extension for AImail v1

- **Status:** Accepted
- **Date:** 2026-04-29
- **Deciders:** MDS25 team
- **Supersedes:** —

## Context

In the 2026-04-27 supervisor meeting, the technical consultant (Alim) demoed a Chrome-extension approach to ingesting Gmail data: a client-side extension that reads Gmail's rendered HTML via XPath selectors and forwards extracted content to the backend. The supervisor expressed enthusiasm for it.

This ADR records the team's decision **not** to adopt that approach for v1, despite the demo being interesting.

The team had already evaluated this option during the proposal phase using a Weighted Scoring Matrix (WSM):

| Approach | WSM Score |
|----------|-----------|
| Tier 2 — Browser extension scraping Gmail UI | **2.70** |
| Tier 3 — Server-side Gmail API via n8n | **4.10** |

Tier 3 (the current architecture) won on academic relevance (4 vs 2), demo readiness (5 vs 2), and AI feature coverage (4 vs 2).

## Decision

**v1 ingestion uses n8n + Gmail API only.** No Chrome extension is built.

## Rationale

- **Architectural fit.** A Chrome extension contradicts the "backend governs everything" principle (see [`../../specs/architecture.md`](../../specs/architecture.md)). Extension-based scraping puts PII on the user's machine, in a browser context, before anything is masked.
- **Brittleness.** Gmail's DOM changes without notice. Every change breaks the extension. n8n's Gmail integration is maintained by n8n's team and Google's stable API.
- **Distribution overhead.** A Chrome extension requires per-user installation, Chrome Web Store review (or sideloading), and update propagation. None of this advances the FYP.
- **Academic framing.** Server-side ingestion + multi-layer LLM processing is the more research-relevant story. UI scraping is a tooling exercise.
- **Scope discipline.** May 10 demo target leaves no slack for an extension. Adding it would put the LLM pipeline at risk.

## Alternatives considered

| Alternative | Why rejected |
|-------------|--------------|
| Build the extension *in addition to* n8n | Doubles ingestion paths, creates a deduplication problem, doubles the surface area to maintain — for no v1 benefit. |
| Replace n8n with the extension | Loses server-side guarantees (PII masking before user's browser sees anything), brittle, narrower (extension only works while Gmail tab is open). |
| Defer the decision to sprint 2 | Scope creep avoidance is cheaper than scope creep recovery. Decide now. |

## Consequences

**Positive**

- Architecture stays clean — one ingestion path, server-side, masked at boundary.
- Sprint 1 stays focused on n8n + listener + backend skeleton.
- No new tech surface (Chrome extension manifest, content scripts, background workers).

**Negative / accepted trade-offs**

- We can't read non-Gmail browser content (e.g., other webmail providers via DOM scraping). Mitigated: Gmail is the explicit v1 scope.
- If a stakeholder pushes for the extension in a future meeting, the team must defend this decision with the WSM. **Reference this ADR.**

## Revisit conditions

Reopen this decision if any of these become true:

- Gmail API is rate-limited or restricted in a way that blocks core functionality.
- A specific FYP requirement emerges that genuinely needs DOM-level access (none currently exists).
- Post-FYP commercialisation requires multi-provider coverage and a unified extension is the cleanest path.

Until then: **the answer is no.**
