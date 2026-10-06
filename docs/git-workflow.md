# Git workflow

How we branch, review, and merge on AImail. Team MDS25.

## Model: one protected `main` (no `prod`)

We use a single long-lived branch, `main` — the integration line and source of truth. We host
locally, so `main` is effectively prod; **we are not using a separate `prod` branch.**

`main` is protected on GitHub:

- No direct pushes. Every change lands via a pull request.
- 1 approving review required, and it must come from a **code owner** (the lead) — see
  [`../.github/CODEOWNERS`](../.github/CODEOWNERS).
- Stale approvals are dismissed when new commits are pushed.
- No force-pushes, no branch deletion.
- Linear history required (we squash-merge).

**Review gate (asymmetric by design):**
- **Everyone except the lead** needs the lead's approval before merging.
- **The lead** is a repo admin and self-merges via admin bypass (admin enforcement is off), so
  the code-owner rule never deadlocks the lead's own PRs. The lead should still invite an
  occasional second look even though it is not enforced.

## The flow

1. **Branch off `main`** for a unit of work:
   ```bash
   git switch main && git pull
   git switch -c feat/<short-description>
   ```
2. **Commit** in [Conventional Commits](https://www.conventionalcommits.org/) format, with a
   `Fixes #<issue>` footer where relevant (see [`../CONTRIBUTING.md`](../CONTRIBUTING.md)).
3. **Push your branch** and open a **pull request into `main`**:
   ```bash
   git push -u origin feat/<short-description>
   gh pr create --base main --fill
   ```
4. **Get the lead's review.** The lead (code owner) reviews and approves; you cannot approve
   your own PR. The lead's own PRs merge via admin bypass, so the code-owner rule does not
   deadlock them.
5. **Squash-merge into `main`** once approved and green. Delete the feature branch.

## Branch naming

- `feat/<thing>` — new feature
- `fix/<thing>` — bug fix
- `docs/<thing>` — docs only
- `chore/<thing>` — tooling, deps, config

## Spec-first

Features begin as a spec (see [`../specs/`](../specs/)) before implementation — a spec PR
against `specs/features/<name>.md` with acceptance criteria, then the implementation PR on a
dedicated branch. Tiny features get tiny specs; they still get one.

## Cross-lane changes

Anything touching a shared contract (`specs/context/api-contracts.md`, `db-schema.md`) or
more than one lane: log the decision in `docs/decisions/shared.md` and update the contract in
the same PR. Flag it in the PR description so the affected lane owner reviews.

## No `prod` branch (decided)

We deliberately do not run a separate `prod`/release branch — hosting locally, a second
protected line is ceremony without payoff. If that ever changes (e.g. a frozen line for a
submission demo), create `prod` from `main`, protect it identically, and promote via
`main -> prod` PRs. Not planned.

---

# Keeping your branch up to date (pull + rebase)

When someone else's PR is merged into `main`, your branch is now **behind** — it was built on an
older `main`. Before you keep working (and before your PR merges), you bring your branch up to
date. We do that with **rebase**, not merge, to keep history linear.

## What a rebase actually is

A rebase **moves your commits so they sit on top of the latest `main`**, as if you had branched
off `main` today instead of yesterday.

```
Before (you branched off an old main; main has moved on):

  main:      A---B---C---D      (D = a teammate's merge you don't have yet)
                  \
  your branch:     E---F        (your two commits, built on B)

After `git rebase main` (your commits replayed on top of D):

  main:      A---B---C---D
                          \
  your branch:             E'---F'   (same changes, new commits on top of D)
```

Your work `E, F` is re-applied on top of `D`. The commits get new IDs (`E'`, `F'`) because their
starting point changed — that's why a rebased branch needs a force-push (below).

**Rebase vs merge:** merging `main` into your branch also gets you up to date, but it adds a
"merge commit" and tangles history. Rebase keeps a straight line, which is what our squash-merge
setup and "linear history" rule want. **Rule of thumb: rebase your *own* feature branch; never
rebase a shared branch like `main`.**

## The everyday loop — do this whenever `main` has moved

```bash
# 1. Get the latest main
git switch main
git pull                      # fast-forwards your local main to match GitHub

# 2. Go back to your branch and replay it on top of the new main
git switch feat/your-thing
git rebase main
```

If nothing conflicts, you're done — your branch now includes everyone else's merged work, with
your commits on top.

## If a rebase hits a conflict

A conflict means you and a teammate changed the same lines. Git pauses and asks you to resolve:

```bash
# Git tells you which files conflict. Open each, find the markers:
#   <<<<<<< HEAD            (what's already on main)
#   =======
#   >>>>>>> your commit     (your change)
# Edit the file to the correct final version and DELETE the marker lines.

git add <the-file-you-fixed>  # mark it resolved
git rebase --continue         # move on to the next commit

# Repeat until the rebase finishes. To bail out entirely and undo the rebase:
git rebase --abort
```

Resolve one commit at a time; git walks your commits `E`, `F` in order.

## After a rebase: force-push (safely)

Because rebasing rewrote your commit IDs, a normal `git push` is rejected. Push with lease — it
overwrites *your* branch on GitHub but refuses if someone else pushed to it meanwhile:

```bash
git push --force-with-lease
```

**Only ever force-push your own feature branch.** Never `--force` to `main` (it's blocked, and it
would rewrite everyone's history). And once a teammate has started reviewing your branch, avoid
rewriting it under them — coordinate first.

## Squashing your branch into one commit (tidy PRs)

Our merge already squashes at merge time, but collapsing your branch into one commit yourself
makes the PR cleaner to review and rebase. Easiest way — reset to `main` keeping your changes,
then commit once:

```bash
git switch feat/your-thing
git reset --soft main         # drop the individual commits, keep every change staged
git commit -m "feat: one clear message for the whole change"
git push --force-with-lease   # rewrites YOUR branch (safe — only yours)
```

`reset --soft main` moves your branch pointer back to `main` while keeping all your changes
staged, so a single commit captures the full diff. Only do this on your own branch. If `main` has
moved, use `git reset --soft $(git merge-base main HEAD)` instead so you don't fold in others'
commits.

# Don't wait to be merged — keep working (branch off your own branch)

You do **not** have to stop and wait for your PR to be reviewed and merged before starting the next
piece of work. Your unmerged branch is a real starting point. Two ways to keep going:

## Option A — keep committing on the same branch

If the next work is *part of the same feature*, just keep committing on the branch you already
opened. New commits show up on the open PR automatically when you push.

```bash
git switch feat/your-thing     # the branch that's already in review
# ...make changes...
git add -p
git commit -m "feat: next piece"
git push                       # updates the existing PR
```

## Option B — stack a new branch on top of your unmerged work

If the next work is *separate* but **needs code from a branch that hasn't merged yet**, branch off
your feature branch instead of `main`. This is called a *stacked branch*.

```bash
# Step 1 — from the branch whose work you need (NOT main):
git switch feat/first-thing

# Step 2 — create the new branch on top of it:
git switch -c feat/second-thing

# Step 3 — work, commit, push as normal:
git add -p && git commit -m "feat: build on the first branch"
git push -u origin feat/second-thing
```

Now `feat/second-thing` contains everything from `feat/first-thing` **plus** your new work, so you
can keep moving while the first branch is still in review.

## Step 4 — after the base branch merges, re-point the stack onto main

Once `feat/first-thing` is merged into `main`, rebase the stacked branch **onto main** so it drops
the now-merged commits and sits cleanly on top:

```bash
git switch main && git pull
git switch feat/second-thing
git rebase --onto main feat/first-thing
git push --force-with-lease
```

`git rebase --onto main feat/first-thing` means: "replay `feat/second-thing`'s commits onto `main`,
removing the commits that came from `feat/first-thing`" (they're already in `main` now, via the
merge). If you skip this and just `rebase main`, you may replay the base commits again and hit
needless conflicts.

**Duplicating to experiment:** the same trick makes a safe copy — `git switch -c feat/experiment`
from any branch gives you a throwaway line to try something without risking the original. Delete it
if it doesn't pan out (`git branch -D feat/experiment`); nothing else is affected.

**Rules for stacked branches:**
- Only stack on **your own** branches, never on a shared branch.
- The deeper the stack, the more rebasing when bases merge — keep stacks 1-2 deep.
- Say so in the PR description ("stacked on #NN") so the reviewer knows the base isn't merged yet.

## Do / don't

- **Do** `git pull` on `main` before branching, and rebase your branch whenever `main` moves.
- **Do** commit or stash your work before rebasing (`git stash`, then `git stash pop` after).
- **Do** use `git push --force-with-lease` (not plain `--force`) after a rebase.
- **Don't** rebase `main` or any shared branch.
- **Don't** force-push a branch someone else is also committing to.
- **Don't** panic on conflicts — `git rebase --abort` always gets you back to before.

## Quick cheat sheet

```bash
git switch -c feat/thing          # start a branch off main
git add -p                        # stage changes (review each hunk)
git commit -m "feat: ..."         # commit (Conventional Commits)
git push -u origin feat/thing     # first push
gh pr create --base main --fill   # open the PR

# main moved? bring your branch up to date:
git switch main && git pull
git switch feat/thing && git rebase main
git push --force-with-lease       # after a rebase

# keep working without waiting to merge (stacked branch):
git switch feat/first-thing       # the unmerged branch you need
git switch -c feat/second-thing   # new work on top of it
# after feat/first-thing merges:
git switch main && git pull
git switch feat/second-thing && git rebase --onto main feat/first-thing

git status                        # what's changed / where am I
git log --oneline -10             # recent history
git switch main                   # jump back to main
git stash / git stash pop         # shelve / restore uncommitted work
```
