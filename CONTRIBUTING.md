# Contributing to AImail

_Last reviewed: 2026-04-29_

This is how we ship work on AImail. Read it once; refer back when stuck. Sprint cadence and ceremonies live in [`docs/scrum.md`](docs/scrum.md).

## The 6-stage flow

```
1. Idea  →  2. Issue  →  3. Spec (features only)  →  4. Branch + commits  →  5. PR + review  →  6. Merge
```
Ideas can be pushed here first and discussed during meetings. When all groupmates agree on an idea, then becomes an issue.
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

> **Phase 0 (current — until first feature ships):** specs in `specs/features/` may be `Status: idea` sketches. The spec-only PR rule and the 4-required-sections rule are aspirational, not gated. Real specs (full template, ACs, etc.) start when a feature is picked up for implementation in sprint 2 or later. The rest of the workflow (commits, branches, PRs, reviews) applies in full.

1. Copy [`specs/_template.md`](specs/_template.md) → `specs/features/<feature-name>.md`.
2. Fill in **Goal**, **Scope**, **Acceptance Criteria**, **API Surface** at minimum.
3. Open a PR with **only the spec** (no code).
4. At least one teammate approves → merge.
5. Now you can start coding.

> _Why a spec-only PR:_ catches misunderstandings cheaply. A 10-minute disagreement over a spec saves a 10-hour rewrite. Tiny features get tiny specs (Goal + AC, six lines) — write it anyway.

Trivially small features (handful of lines, no contract change) **may** bundle spec + code in one PR if the reviewer is comfortable. Default is two PRs.

---

## 3 · Branch + commits

### Branches

Branch off `main`, kebab-case, short:

| Prefix    | Use for                            | Example                      |
|-----------|------------------------------------|------------------------------|
| `feat/`   | new feature                        | `feat/pii-masking`           |
| `fix/`    | bug fix                            | `fix/draft-empty-body`       |
| `chore/`  | tooling, deps, refactor            | `chore/add-ruff`             |
| `docs/`   | documentation only                 | `docs/scrum-cadence`         |
| `spec/`   | spec-only PRs (stage 2)            | `spec/style-learning`        |

Rules:

- **Every branch references an open issue.** No issue → no branch. If you start typing code without an issue, stop and create one.
- **One issue per branch.** Don't bundle three issues into one branch — each should land in its own PR.
- **Optionally embed the issue number** in the branch name: `feat/42-pii-masking`. Useful for grep but not required.
- Branches live no longer than the sprint. Anything older gets rebased onto `main` or closed.

### Commits

Commits use [Conventional Commits](https://www.conventionalcommits.org/). Full anatomy:

```
<type>(<scope>): <subject>            ← line 1, ≤ 72 chars, imperative, no period
                                       ← blank line (mandatory)
<body — what changed and why>          ← wrap at 72 chars, bullet points OK
- bullet
- bullet
                                       ← blank line (mandatory before footer)
Fixes #<issue-number>                  ← footer: links the commit to the issue
```

**Real example:**

```
feat(backend): add PII masking endpoint

- Mask email body via regex passes for emails, phone numbers, names.
- Return both masked text and a token map for un-masking on egress.
- Add 6 pytest cases covering the edge cases listed in the spec.

Fixes #42
```

### Subject line rules

- **Type** — one of: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`, `style`, `spec`.
- **Scope** — one of: `backend`, `frontend`, `listener`, `n8n`, `infra`, `specs`, `repo`.
- **Subject** — imperative mood (`add`, `fix`, `remove` — not `added` / `adds` / `added the`).
- **Length** — ≤ 72 chars total. GitHub truncates at 72.
- **No period** at the end. It's a title, not a sentence.
- **Lowercase** subject (except proper nouns).

### Body rules (skip for trivial commits)

- Blank line between subject and body — non-negotiable, git relies on it.
- Wrap at 72 chars per line.
- Explain the **why**, not the what — the diff already shows what.
- Bullet points are fine. Two-three points beats one wall of text.
- Reference design docs, specs, or external links if the reasoning is somewhere else.

### Footer rules

- **`Fixes #N`** — closes issue N when the PR squash-merges. Use for "this commit completes the issue."
- **`Refs #N`** — links to issue N without auto-closing. Use when partially addressing.
- **`Closes #N`** — synonym for `Fixes`. Pick one and stick with it (we use `Fixes`).
- **`Co-authored-by: Name <email>`** — for pair work. One line per co-author.
- **`BREAKING CHANGE:`** — when a public contract changes incompatibly. Add a paragraph after this line explaining what consumers must do.

### Commit anti-patterns to avoid

- `wip` / `fix typo` / `update` / `idk` as subjects → squash these into the parent commit before pushing.
- Commits that mix unrelated changes (formatting + new feature in one commit). Split them.
- Commits that don't compile or pass tests → rebase to fix before pushing.
- Force-pushing after a review starts on the PR — breaks reviewer threads (covered in §5).

> _Why this much detail:_ the squash commit on `main` becomes part of your final report's auto-generated changelog. The body is what your examiner reads when they ask "why did you do X?" Six months from now you'll thank past-you for writing it.

Commit small and often — one logical change per commit. `git log` on a branch should read like a story.

---

## 4 · Pull request

### Before you open the PR — rebase onto `main`

Always sync your branch with `main` before pushing for review. Stops drift, reduces merge conflicts, lets CI test against current `main`.

```bash
git checkout main
git pull
git checkout <your-branch>          # e.g. feat/pdf-email-attach
git rebase main
```

If the rebase hits conflicts, resolve them locally, then `git rebase --continue`. Don't `git rebase --abort` and merge instead — keeps history clean.

After a successful rebase, force-push your branch (this is fine **before** review starts):

```bash
git push --force-with-lease
```

`--force-with-lease` is safer than `--force` — it refuses to overwrite the remote if someone else pushed to your branch in the meantime.

> **Once a reviewer has started commenting, stop rebasing.** Force-pushing after review breaks comment threads. Add new commits on top instead; they all squash at merge anyway. (Same rule as §5.)

### Push and open

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

## Other conventions worth knowing

### Files & naming

- Markdown / docs → `kebab-case.md`. Specs in `specs/features/<feature>.md`.
- Code files → language convention (`snake_case.py`, `kebab-case.ts` for non-components, `PascalCase.tsx` for React components, `snake_case.go`).
- DB migrations → `<timestamp>_<verb>_<table>.py` (e.g. `20260429_create_chat_table.py`).
- Test files → mirror the path of the file under test, with `_test.py` / `.test.ts` / `_test.go` suffix.

### Environment files

- **`.env` is gitignored. `.env.example` is committed.** When you add a new env var to `.env`, update `.env.example` in the same commit with a placeholder value. PR will be rejected if these drift.
- Same rule for `infra/docker-compose.yml` env vars.

### Lockfiles

- `package-lock.json` (or `pnpm-lock.yaml`), `poetry.lock` (or `requirements.txt` if pip-only), `go.sum` — **always commit them.** They are why builds are reproducible.
- Never gitignore them. If you see them in `.gitignore`, that's a bug.

### Tests & code health

- Non-trivial logic ships with tests. "Non-trivial" = anything with branches, transformations, or external calls.
- **Never delete a failing test to make CI green.** Fix the cause or open an issue and skip with `@pytest.mark.skip(reason="#42")` linking the issue.
- No commented-out code in commits. Use git history if you need to recover something.
- Type-check and lint before pushing. Don't let CI find what your editor would have.

### Specs & docs that must stay in sync

- API shape changes → update `specs/context/api-contracts.md` in the **same PR** as the code.
- DB schema changes → update `specs/context/db-schema.md` in the **same PR** as the migration.
- User-visible behavior changes → update the relevant service README in the same PR.
- Spec-implementation drift → update the spec in the same PR; never let them disagree on `main`.

### PRs & issues

- Cross-link related issues in the PR body (`Refs #41, #43`) — even if they're not closed by this PR.
- Convert PR to **draft** while still in progress; promote to "Ready for review" only when you genuinely want eyes on it.
- One issue → one PR. If a PR closes multiple issues, that's a sign the issues should have been one issue, or the PR should be split.

### Releases & changelog

- We use **Release Please** (Google's GitHub Action) to auto-generate `CHANGELOG.md` from Conventional Commits. See [`docs/release-process.md`](docs/release-process.md) for the full flow.
- Don't hand-edit `CHANGELOG.md`. It's regenerated.
- Don't write to `package.json` / `pyproject.toml` version fields manually — Release Please bumps them.

### Security

- Secrets scanning runs on every push (TODO — `gitleaks` or GitHub native). If it flags a commit, **don't force-push to hide it** — rotate the secret first, then clean history.
- Never paste a real API key, even in a private channel. Use `.env.example` placeholder syntax: `ANTHROPIC_API_KEY=<your-key-here>`.

---

## Enforcement

Rules only matter if someone enforces them, but real-time enforcement burns reviewers out. We do it in **retro**, not in PR comments. Don't chase every missed label; raise patterns at the end of the sprint ("four PRs landed without spec links — let's tighten that"). Once the project board is wired up, most enforcement happens automatically through templates and required fields.
