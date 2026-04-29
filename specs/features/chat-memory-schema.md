# Chat memory (idea)

- **Status:** idea
- **Owner:** TBD
- **Last updated:** 2026-04-29

> **Status: idea.** This is a pre-implementation sketch. The concepts here are core to AImail, but specific shapes (table layout, function signatures, ACs) will be decided when this feature is picked up for implementation. Promoted to a full spec at that point — see [`../_template.md`](../_template.md).

## Goal

Persist every email-thread-to-AI interaction as a chat-style memory, so the agent has continuous context across replies and so the team has empirical data for the FYP evaluation chapter.

## Why this matters

- **Continuous context.** Each new email in a thread is one turn in an ongoing conversation with the model — not an isolated event. The agent needs prior turns to reply coherently.
- **FYP evaluation data.** Storing **both** the AI's draft and the user's edited final reply gives us an empirical signal — how much was changed, how that drifts over time, where the system improves. This is the data the report's evaluation chapter will lean on.
- **Memory backbone.** Every layer of the agent pipeline ([`../agent-pipeline.md`](../agent-pipeline.md)) reads from and writes to this memory. Without it, the pipeline has no continuity.

## Non-negotiables (lock these in)

- **Capture both versions.** AI's generated draft AND the user's final edited text are stored, separately, on every approved reply. Losing either kills the eval angle.
- **Parent/child shape.** Threads-as-chats with conversation-turns-as-children is the right framing. The exact column list is open.
- **Masked text only.** Anything written to these tables is post-PII-masking. PII never lands here in raw form.

## Open shape (rough sketch — not binding)

A parent record represents one email thread treated as an LLM conversation. It has many child rows representing individual generation events (classifier call, reasoner call, drafter call, evaluator pass). Drafts surfaced to the user are tracked separately, with a feedback row capturing what the user picked and edited. Vector search over historical replies for style retrieval is a separate concern.

## What we'll figure out at implementation time

- Exact column layout and types.
- 1:1 vs 1:N between threads and chats.
- How many recent turns get included as context per new generation.
- Edit-distance unit (char vs word).
- Retention policy.
- Whether the conversation rows store full prompt + context, or just references.
- Whether vector embeddings live in this table or a separate one.

## Depends on / feeds into

- **Depends on:** `thread` and `user` tables (sketched in [`../context/db-schema.md`](../context/db-schema.md)).
- **Feeds into:** the agent pipeline's memory layer ([`../agent-pipeline.md`](../agent-pipeline.md)), model feedback routing ([`./model-feedback-routing.md`](./model-feedback-routing.md)), eventual style profile.
