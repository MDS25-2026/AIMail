# Sprint cadence & ceremonies

_Last reviewed: 2026-04-28_

How we run sprints on AImail. The development workflow (issue → PR → merge) lives in [`../CONTRIBUTING.md`](../CONTRIBUTING.md). This file is about **rhythm** — when we plan, when we sync, when we review.

Specifics marked `TBD` are filled in by the team during the first sprint.

---

## Cadence

| Field            | Value                  |
|------------------|------------------------|
| Sprint length    | TBD (1 week or 2 weeks) |
| Sprint starts    | TBD (e.g. Monday 9am)   |
| Sprint ends      | TBD (last working day)  |
| Timezone         | MYT (Asia/Kuala_Lumpur) |

A sprint contains a fixed set of issues agreed at planning. New work that comes up mid-sprint goes to the backlog unless it's a `P0`.

---

## Ceremonies

### Sprint planning

- **When:** first day of the sprint.
- **Who:** all four team members.
- **Time-box:** TBD (target 60 min).
- **Inputs:** groomed backlog of issues meeting the **Definition of Ready**.
- **Output:** sprint board populated with issues + assignees, with rough effort sizing.
- **Rule:** no issue enters the sprint without an area label, type label, priority, and (for features) a merged spec.

### Daily standup

- **When:** every working day. Time TBD.
- **Format:** async-first — post in the team chat. Sync only if blocked.
- **Each person posts:**
  1. What I shipped since the last standup.
  2. What I'm shipping next.
  3. Blockers (tag whoever can unblock).
- **Time-box:** under 5 min to read; under 15 min if sync.

### Sprint review

- **When:** last day of the sprint.
- **Who:** team + supervisor (Dr. Asad Malik) when relevant.
- **Time-box:** TBD (target 30 min).
- **Output:** demo of what shipped; written summary in the sprint's GitHub Discussion or a `docs/sprint-reviews/<n>.md` (TBD).

### Retrospective

- **When:** immediately after sprint review.
- **Who:** team only.
- **Time-box:** 30 min.
- **Format:** three columns — **Keep / Stop / Start.** One concrete action item per retro, owner assigned, tracked as a GitHub issue with the `chore` label.

---

## Definition of Ready

An issue is **Ready** (eligible for sprint planning) when:

- [ ] Title is descriptive.
- [ ] Area, type, and priority labels set.
- [ ] Acceptance criteria written.
- [ ] For features: linked spec exists and is merged (`status: spec-pending` is cleared).
- [ ] No unanswered open questions in the issue thread.

Issues that aren't Ready stay in the backlog and get groomed before the next planning.

---

## Definition of Done

Work is **Done** when:

- [ ] PR is squash-merged into `main`.
- [ ] All acceptance criteria verifiably met.
- [ ] Linked issue closed (auto-closes via `Closes #N`).
- [ ] Spec **Status** updated to `shipped`.
- [ ] No open `P0`/`P1` regressions introduced.
- [ ] Any contract changes reflected in `specs/context/api-contracts.md` or `specs/context/db-schema.md`.

`Done` is binary. Half-done work stays in the sprint or rolls over — it doesn't count toward velocity.

---

## Backlog hygiene

- **Grooming:** mid-sprint, ~30 min. Whoever has bandwidth picks up unlabeled or unclear issues and either fixes them, asks the author, or closes them.
- **Stale issues:** anything untouched for 30 days gets a comment asking if it's still relevant. No reply in 7 days → close with `wontfix`.
- **Epics:** reviewed at every planning. If no child task moved in two sprints, decide whether to descope.

---

## What this doc is not

- Not a process bible. If a rule here is causing more friction than value, raise it in retro and change it.
- Not GitHub UI documentation — labels, board automations, and branch protection rules live in repo settings, not here.
- Not the development workflow — see [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for branch / commit / PR rules.
