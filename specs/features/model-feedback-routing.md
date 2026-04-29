# Model feedback routing (idea)

- **Status:** idea
- **Owner:** TBD
- **Last updated:** 2026-04-29

> **Status: idea.** This is a pre-implementation sketch. The concepts here are core to AImail, but specific shapes (table layout, function signatures, ACs) will be decided when this feature is picked up for implementation. Promoted to a full spec at that point — see [`../_template.md`](../_template.md).

## Goal

Use real user feedback (which draft got picked, what got edited, thumbs up/down) to dynamically choose which model handles each layer of the agent pipeline. Start with multiple candidate models per layer; narrow toward the winner per user as data accumulates.

## Why this matters

- **The FYP differentiator.** A system that quantifiably gets better with use is a much stronger story than a system that "calls Claude well." The trajectory of *mean edit distance over time per user* is the single chart that demonstrates learning.
- **Avoids premature lock-in.** We don't have to pick "the best model" up front. The data picks. Models we shortlist in [`../context/tech-stack.md`](../context/tech-stack.md) compete; usage selects winners.
- **Per-user adaptation.** Different users have different writing styles. The model that wins for one user may not win for another. Routing per user means the system tunes itself to each person.

## Non-negotiables (lock these in)

- **Cold start = randomise.** Until a user has enough feedback, we sample across the candidate pool. No hard-coded default.
- **The signal is observable behavior.** Edit distance + thumbs is the data. Not surveys, not self-reporting.
- **The chart is the deliverable.** Edit-distance-over-time (per user, per model) goes in the FYP report. Whatever we build must be able to produce it.

## Open shape (rough sketch — not binding)

For each user and each layer of the pipeline (classifier / reasoner / drafter / evaluator), we maintain a notion of "current best model" plus the candidate pool. A periodic aggregation job reads accumulated feedback and updates the assignment. Selection at request time is some flavor of bandit (epsilon-greedy is the obvious starting point). Pools live in code config; assignments live in the DB.

## What we'll figure out at implementation time

- How many feedback rows trigger the switch from random to personal-best.
- Aggregation cadence (real-time vs batch nightly vs hourly).
- Score formula — simple normalised mean, UCB1, Thompson sampling, or something else.
- Whether to expose model-used to the user.
- Whether cross-user defaults get learned (and weighted into cold start).
- The exact bandit strategy.

## Depends on / feeds into

- **Depends on:** feedback data captured by [`./chat-memory-schema.md`](./chat-memory-schema.md).
- **Depends on:** candidate pools defined alongside the agent pipeline — see model tiers in [`../context/tech-stack.md`](../context/tech-stack.md).
- **Feeds into:** the FYP evaluation chapter (the learning-curve chart).
