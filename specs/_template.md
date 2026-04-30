# <Feature name>

<!-- Copy this file into specs/features/<kebab-case-name>.md and fill in. Delete this comment when done. -->

- **Status:** draft <!-- idea | draft | approved | in-progress | shipped | archived -->
- **Owner:** <github handle>
- **Related issue:** #
- **Last updated:** YYYY-MM-DD

## Goal

<!-- One or two sentences. What problem does this feature solve? -->

## User story

<!-- As a <user>, I want <capability>, so that <benefit>. -->

## Scope

**In scope**
- <thing 1>
- <thing 2>

**Out of scope**
- <thing 1>

## Acceptance criteria

<!--
Each AC must be observable, binary, and runnable as a check.
Pattern: "Given <state>, when <action>, then <observable outcome>."
If you can't imagine writing a test or manual check for it, sharpen it.
See specs/README.md → "Acceptance criteria must be testable".
-->

- [ ] Given …, when …, then …
- [ ] Given …, when …, then …

## API surface

<!-- HTTP endpoints, function signatures, or webhook shapes this feature exposes or consumes. Keep request/response examples short. Link to specs/context/api-contracts.md if updating shared contracts. -->

## Data model

<!-- New tables / columns / vector indexes. Link to specs/context/db-schema.md if updating shared schema. -->

## Dependencies

<!-- Other specs, services, libraries, or external APIs this feature depends on. -->

## Edge cases & failure modes

<!-- What can go wrong? Empty inputs, network failures, rate limits, partial state, concurrent edits. How does the system behave? -->

## Security & privacy notes

<!-- PII handling, secrets, authz boundaries, data retention. AImail's PII masking flow MUST be considered for anything that touches email content. -->

## Open questions

<!-- Things we don't know yet. Decisions that need to be made. -->

## Out-of-scope future extensions

<!-- Ideas that are tempting but explicitly deferred. -->

## Implementation notes

<!-- Non-binding hints for whoever picks this up. Tradeoffs considered, libraries suggested, files likely to change. -->

## Decisions

<!--
Record architectural choices made while implementing this feature.
For decisions that affect more than this feature, open an ADR in
docs/adr/ instead and link it here.

Format:
  - YYYY-MM-DD: <decision>. Rationale: <one line>. Alternatives: <one line>.
-->

## Protected decisions

<!--
For non-negotiable choices that future agents must not silently change.
Wrap the rule in the markers below — do not remove without explicit approval.

<!-- BEGIN PROTECTED -->
[Critical decision with rationale]
DO NOT change this without [approval condition].
<!-- END PROTECTED -->
-->

