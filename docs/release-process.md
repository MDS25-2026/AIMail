# Release process

How AImail releases are cut. Mostly automated — humans only intervene at merge time.

_Last reviewed: 2026-04-29_

---

## Tooling

- **[Release Please](https://github.com/googleapis/release-please)** — Google's GitHub Action that watches `main`, parses Conventional Commits, and maintains an open release PR.
- Config lives in [`/release-please-config.json`](../release-please-config.json).
- Version state lives in [`/.release-please-manifest.json`](../.release-please-manifest.json).
- Workflow lives in [`/.github/workflows/release-please.yml`](../.github/workflows/release-please.yml).

---

## How a release happens

1. **You push commits to `main`** (via merged PRs, following the [Conventional Commits](../CONTRIBUTING.md#commits) rules).
2. **Release Please runs on each push.** It scans commits since the last release.
3. **It opens (or updates) a single PR** titled `chore: release vX.Y.Z`. This PR contains:
   - The new entry appended to [`/CHANGELOG.md`](../CHANGELOG.md).
   - The new version written into [`/.release-please-manifest.json`](../.release-please-manifest.json).
4. **You review and merge the release PR** when you want to cut the release. Reviewing is mostly sanity-checking: does the changelog read sensibly? Did anything important not surface?
5. **On merge, Release Please:**
   - Creates a git tag (`vX.Y.Z`).
   - Creates a GitHub Release with the changelog entry as the body.
   - Closes the release PR.

You can let the release PR sit open across multiple feature merges — it auto-updates. Merge it whenever you want a release marker.

---

## Version-bumping rules (pre-1.0)

While we are below `1.0.0`:

| Commit type    | Version effect          |
|----------------|-------------------------|
| `feat:`        | minor bump? **No** — patch bump (project is pre-1.0). |
| `fix:`         | patch bump.             |
| `BREAKING CHANGE:` footer | minor bump (allowed pre-1.0).      |
| Anything else  | no version effect by itself; rolls into the next bumping commit. |

This is enforced by the `bump-patch-for-minor-pre-major: true` flag in [`/release-please-config.json`](../release-please-config.json). It keeps version churn minimal until we're ready to cut a real `1.0.0` for the FYP demo.

When you're ready for `1.0.0`, edit `.release-please-manifest.json` (or comment `release-as: 1.0.0` on the release PR) and merge.

---

## What ends up in the changelog

Configured in `changelog-sections` of [`/release-please-config.json`](../release-please-config.json). Currently:

| Commit type | Changelog section | Visible? |
|-------------|-------------------|----------|
| `feat`      | Features          | yes |
| `fix`       | Bug Fixes         | yes |
| `perf`      | Performance       | yes |
| `refactor`  | Refactoring       | yes |
| `docs`      | Documentation     | yes |
| `test`      | Tests             | yes |
| `spec`      | Specifications    | yes |
| `chore`     | Chores            | hidden |
| `style`     | Style             | hidden |

The full list is intentionally broader than the typical "feat / fix only" because the FYP report benefits from a complete record of work. `chore` and `style` are hidden because they're noise.

To **change** what's visible, edit `changelog-sections` and merge — the next release PR uses the new config.

---

## Anti-patterns

| Don't | Why |
|-------|-----|
| Hand-edit `CHANGELOG.md`. | Release Please regenerates it. Your edits get clobbered or cause merge conflicts. |
| Manually create a `chore: release` commit. | Release Please does this. Doing it yourself confuses the next run. |
| Manually tag releases (`git tag v0.1.0`). | Release Please tags on PR merge. Manual tags break version detection. |
| Force-push to `main`. | Release Please's commit history scan breaks. Already prevented by branch protection. |
| Squash-merge the release PR. | Release PRs should **merge commit** — Release Please relies on merge commit metadata. *(See note below.)* |

### Release PR merge style

Release PRs are the **one exception** to our squash-only rule. Their merge commit is structurally meaningful — Release Please reads it to confirm the release happened. Configure GitHub to allow merge commits **for the release PR only** (or merge it via the GitHub CLI explicitly with `gh pr merge --merge`).

If your branch protection blocks merge commits entirely, either:

1. Temporarily allow merge commits, merge the release PR, switch back. Or
2. Use `gh pr merge <release-pr> --rebase` — Release Please supports this when paired with the `release-please-action`'s default tag detection.

Document whichever you pick here so the next person doesn't relitigate it.

---

## What Release Please does NOT do

- **Run tests.** That's CI's job (separate workflow). A release PR can land even if tests fail unless you wire CI as a required check on it.
- **Push to a package registry.** No `npm publish` / `pip upload`. AImail isn't published as a package — only tagged in git.
- **Notify anyone.** Slack / email / Discord webhooks need to be added separately if you want them.

---

## When something goes wrong

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| No release PR appears after merging features | Workflow didn't run, or no Conventional Commits since last release | Check Actions tab → release-please run logs. Verify commit messages are Conventional. |
| Release PR includes commits that should have been hidden | A `chore:` or `style:` accidentally got typed as `feat:` | Amend in a follow-up commit; release PR auto-refreshes. |
| Version bumped wrong | A `BREAKING CHANGE:` footer was misread | Comment `release-as: <correct-version>` on the release PR. Release Please obeys. |
| Want to skip a release | Don't merge the release PR. It stays open and accumulates. | Merge whenever ready. |

---

## Status

**Status:** active.
**Last release:** none yet. Project is at `0.0.0`.
