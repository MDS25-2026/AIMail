# ADR 0002 — Orchestration framework choice (LangChain vs. direct SDK)

- **Status:** Proposed — **decision pending team meeting**
- **Date opened:** 2026-04-29
- **Deciders:** MDS25 team (decision deferred)
- **Supersedes:** —

## Context

In the 2026-04-27 supervisor meeting, Alim referenced "long chain" (LangChain) as a way to chain LLM calls together for the multi-layer pipeline described in [`../../specs/agent-pipeline.md`](../../specs/agent-pipeline.md).

The team needs to decide whether to:

1. Use **LangChain / LangGraph** (Python framework for chaining LLM calls), or
2. Use **direct Anthropic SDK calls** with hand-rolled async orchestration (`asyncio.gather` for fan-out, plain Python for sequencing).

This ADR documents both sides so the team can decide at the next meeting. **No decision has been made.**

## Options

### Option A — LangChain / LangGraph

**Pros**

- Built-in primitives for multi-step pipelines, memory, tool use, RAG.
- Large ecosystem of tutorials, examples, integrations.
- LangGraph specifically models DAG-style flows — fits our classifier → reasoner → drafter shape well.
- Familiar pattern if anyone on the team already knows it.

**Cons**

- Heavy abstraction over what is fundamentally "call API, process, call API again."
- Debugging across abstraction layers is painful when things break.
- Industry sentiment has shifted: many teams have removed LangChain after hitting leaky abstractions.
- Anthropic's own docs recommend direct SDK usage with simple patterns for most cases.
- Adds a non-trivial dependency surface for a 12-week project.

### Option B — Direct Anthropic SDK + hand-rolled orchestration

**Pros**

- Smallest dependency surface. One SDK, plus `asyncio` / `httpx` from stdlib.
- Total control over retries, timeouts, error handling, logging.
- Easier to reason about for new contributors — no framework concepts to learn.
- Aligns with Anthropic's recommended pattern.
- Code maps 1:1 to the agent-pipeline spec — no abstraction layer to translate through.

**Cons**

- We re-implement primitives LangChain provides for free (memory abstraction, prompt templates, retry decorators).
- Boilerplate grows as the pipeline grows; ~200 lines for the orchestration layer is plausible.
- No built-in tracing/eval tooling — would have to roll our own observability.

## Recommendation (for the meeting to evaluate)

**Provisional lean: Option B (direct SDK)**, because:

- The pipeline shape ([`../../specs/agent-pipeline.md`](../../specs/agent-pipeline.md)) is small enough that LangChain's abstractions don't pay for themselves.
- FYP scope rewards transparency — the examiner can read the orchestration code and follow it. LangChain hides flow inside framework calls.
- If we hit a primitive we genuinely need (e.g., RAG retrieval), we can pull in a single targeted dependency (e.g., `chromadb` or pgvector queries directly) without committing to the whole framework.

This lean is **not binding**. The team should weigh it against:

- Whether anyone on the team already has LangChain experience.
- Whether the supervisor specifically wants LangChain visible in the deliverable.
- Whether we'd use enough of LangChain's primitives to justify the dependency.

## Decision required by

Before the first agent-pipeline implementation PR. Sprint 2 latest. Pin the choice here, then update [`../../specs/context/tech-stack.md`](../../specs/context/tech-stack.md) to reflect it.

## Consequences

Both options have downstream effects on the project layout:

- **If A:** `backend/app/agents/` becomes LangChain chains/graphs. Tech stack adds `langchain`, `langgraph` as deps. Docs link to LangChain conventions.
- **If B:** `backend/app/agents/` is plain Python modules — `classifier.py`, `reasoners.py`, `drafter.py`, `evaluator.py`, plus an `orchestrator.py` that wires them with `asyncio`.

Either choice can be reversed later, but the cost grows fast. Aim to lock in by sprint 2.

## Open question for the meeting

> Does anyone on the team have a strong preference, prior experience, or concrete blocker that should drive this decision?

Bring concrete examples (good or bad) of LangChain in past projects if anyone has them.
