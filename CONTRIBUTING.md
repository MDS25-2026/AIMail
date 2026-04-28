# Contributing to AImail

_Last reviewed: 2026-04-28_

This is how we ship work on AImail. Read it once; refer back when stuck. Sprint cadence and ceremonies live in [`docs/scrum.md`](docs/scrum.md).

## The 6-stage flow

```
1. Idea  →  2. Issue  →  3. Spec (features only)  →  4. Branch + commits  →  5. PR + review  →  6. Merge
```

If something's not in GitHub, it doesn't exist. WhatsApp ideas die in WhatsApp.

---

## 1 · Issue

Use one of the templates: `task.md`, `bug.md`, `research.md`, or `epic.md`.

Every issue must have:

- **Title** — descriptive (`Add PII masking endpoint`, not `masking thing`).
- **Area label** — `area: backend` / `frontend` / `listener` / `n8n` / `infra` / `docs` / `specs`.
- **Type label** — `type: feat` / `bug` / `chore` / `research`.
- **Priority** — `P0` (blocker) / `P1` (this sprint) / `P2` (later).
- **Assignee** — only when someone's actively starting it. Unassigned = up for grabs.

Features without a spec yet get the `status: spec-pending` label until stage 2 produces one.

> _Why so many labels:_ the project board (coming soon) filters by them. Skipping labels means your issue is invisible during planning.

---

## 2 · Spec (features only — bugs and chores skip this)

1. Copy [`specs/_template.md`](specs/_template.md) → `specs/features/<feature-name>.md`.
2. Fill in **Goal**, **Scope**, **Acceptance Criteria**, **API Surface** at minimum.
3. Open a PR with **only the spec** (no code).
4. At least one teammate approves → merge.
5. Now you can start coding.

> _Why a spec-only PR:_ catches misunderstandings cheaply. A 10-minute disagreement over a spec saves a 10-hour rewrite. Tiny features get tiny specs (Goal + AC, six lines) — write it anyway.

Trivially small features (handful of lines, no contract change) **may** bundle spec + code in one PR if the reviewer is comfortable. Default is two PRs.

---

## 3 · Branch + commits

Branch off `main`, kebab-case, short:

| Prefix    | Use for                            | Example                      |
|-----------|------------------------------------|------------------------------|
| `feat/`   | new feature                        | `feat/pii-masking`           |
| `fix/`    | bug fix                            | `fix/draft-empty-body`       |
| `chore/`  | tooling, deps, refactor            | `chore/add-ruff`             |
| `docs/`   | documentation only                 | `docs/scrum-cadence`         |
| `spec/`   | spec-only PRs (stage 2)            | `spec/style-learning`        |

Commits use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `style`.
Scopes: `backend`, `frontend`, `listener`, `n8n`, `infra`, `specs`, `repo`.

Examples:

- `feat(backend): add PII masking endpoint`
- `fix(frontend): handle empty thread state`
- `docs(specs): add reply-generation spec`

Commit small and often — one logical change per commit. `git log` should read like a story.

> _Why Conventional Commits:_ auto-generates a clean changelog for the final report, looks professional to the examiner, and forces you to name what each commit does.

---

## 4 · Pull request

```bash
git push -u origin <branch>
```

Open the PR against `main`. The PR template fills in automatically. Required:

- Title in Conventional Commits format.
- Linked issue (`Closes #42`).
- Linked spec for features.
- Screenshots for any frontend change.
- Testing notes (what you ran, what passed).

Rules:

- **One approval** required before merge.
- **No self-merge.** Exception: doc-only fixes after 24h with no reviewer available.
- **Squash and merge** — one commit per feature on `main`. Keep the squashed message Conventional.

> _Why squash:_ `main` history stays readable. Each line in `git log main` is one shipped feature, not 17 fixup commits.

---

## 5 · Review

**Reviewer SLA:** respond within 24h on weekdays, 48h on weekends.

Reviewer checklist:

- Read the spec before the diff.
- Skim every changed file. `LGTM` alone isn't a review.
- Block on: missing tests for non-trivial logic, secrets in the diff, contract drift not in `specs/context/`, dependency additions without prior discussion.
- Comment on **why**, not just **what**. Suggest, don't dictate.
- Mark optional comments `nit:` so the author can ignore them.
- If you don't understand something, ask. If the author can't explain it, that's a signal.

Author etiquette:

- Reply to every comment (fix it, or push back with reasoning).
- **No force-push after review starts** — breaks reviewer comment threads. Add commits on top; squash happens at merge.
- Don't take comments personally. Reviewers attack code, not people.

---

## 6 · Merge

Click **Squash and merge**. Then:

- Branch auto-deletes (repo setting).
- Linked issue auto-closes (`Closes #42` in the PR description).
- Project board moves the card to **Done**.

Author's post-merge job:

- Update the spec's **Status** to `shipped`.
- If implementation diverged from the spec, add a note in the spec's **Implementation notes**.

---

## Labels reference

| Group    | Labels                                                                                  |
|----------|-----------------------------------------------------------------------------------------|
| Area     | `area: backend`, `area: frontend`, `area: listener`, `area: n8n`, `area: infra`, `area: docs`, `area: specs` |
| Type     | `type: feat`, `type: bug`, `type: chore`, `type: research`                              |
| Priority | `P0`, `P1`, `P2`                                                                        |
| Status   | `status: spec-pending`, `status: blocked`, `status: in-review`                          |

---

## Enforcement

Rules only matter if someone enforces them, but real-time enforcement burns reviewers out. We do it in **retro**, not in PR comments. Don't chase every missed label; raise patterns at the end of the sprint ("four PRs landed without spec links — let's tighten that"). Once the project board is wired up, most enforcement happens automatically through templates and required fields.
