# ADR 0002 — Orchestration framework choice (LangChain vs. direct SDK)

- **Status:** Accepted
- **Date opened:** 2026-04-29
- **Date accepted:** 2026-05-07
- **Deciders:** MDS25 team
- **Supersedes:** —

## Context

In the 2026-04-27 supervisor meeting, Alim referenced "long chain" (LangChain) as a way to chain LLM calls together for the multi-layer pipeline described in [`../../specs/agent-pipeline.md`](../../specs/agent-pipeline.md).

The team needed to decide whether to:

1. Use **LangChain / LangGraph** (Python framework for chaining LLM calls), or
2. Use **direct Anthropic SDK calls** with hand-rolled async orchestration (`asyncio.gather` for fan-out, plain Python for sequencing).

## Decision

**AImail uses direct Anthropic SDK calls with `asyncio`-based orchestration.** LangChain and LangGraph are not adopted.

## Rationale

- **Pipeline shape maps 1:1 to Anthropic's published patterns.** The classifier → reasoners → drafter + evaluator pipeline is *Routing + Parallelization + Evaluator-optimizer* from Anthropic's "Building Effective Agents" guide. Reference implementations of all three exist as short direct-SDK examples. A framework would translate that code into framework concepts without adding capability.
- **Performance evidence rejects the alternative.** The supervisor flagged LangChain as too slow in prior work. A team member's internship using LangGraph on a comparable pipeline confirmed similar latency overhead. With a 60-second end-to-end sprint-1 budget (see [`../../specs/agent-pipeline.md`](../../specs/agent-pipeline.md)), framework overhead is unacceptable.
- **Examiner-readability matters.** FYP scoring rewards code an examiner can follow. `asyncio.gather(summary(), actions(), intent())` is parseable in seconds. A LangGraph state graph requires the reader to learn LangGraph first.
- **Reversibility is cheap.** If a future sprint genuinely needs DAG checkpointing or human-pause-mid-pipeline, porting only the orchestrator to LangGraph is a one-day job because each layer is a pure function. Those features are not needed today.
- **Smallest dependency surface.** One SDK plus stdlib `asyncio`. No framework version churn, no abstraction layers to debug through.

## Alternatives considered

### LangChain / LangGraph

**Pros**

- Built-in primitives for multi-step pipelines, memory, tool use, RAG.
- Large ecosystem of tutorials and integrations.
- LangGraph specifically models DAG-style flows.

**Cons**

- Heavy abstraction over what is fundamentally "call API, process, call API again."
- Debugging across abstraction layers is painful when things break.
- Industry sentiment has shifted: many teams have removed LangChain after hitting leaky abstractions.
- Anthropic's own docs recommend direct SDK usage with simple patterns for most cases.
- Concrete latency concerns from team members' prior experience (see Rationale).
- Non-trivial dependency surface for a 12-week project.

The pros do not outweigh the latency cost or the readability cost for this project's shape.

## Consequences

- `backend/app/agents/` is plain Python modules — `classifier.py`, `reasoners.py`, `drafter.py`, `evaluator.py`, plus an `orchestrator.py` that wires them with `asyncio`.
- `pyproject.toml` does **not** add `langchain` or `langgraph` deps.
- We re-implement primitives LangChain provides for free (memory abstraction, prompt templates, retry decorators). Each is small, written when first needed, no earlier.
- No built-in tracing/eval tooling — replaced by a structured-logging decorator on each layer.
- Boilerplate grows linearly with the pipeline; ~200 lines for the orchestration layer is plausible. This is accepted.

## Revisit conditions

Reopen this decision if any of these become true:

- The pipeline grows to need stateful pause/resume across hours or days (e.g., human-in-the-loop at multiple checkpoints) and DB rows are no longer enough to model it.
- A specific Anthropic SDK capability lands behind LangGraph integration only.
- A second-product use case appears that needs RAG over many sources, where LangChain's retrieval primitives would save meaningful work.

Until then: **the answer is direct SDK.**
