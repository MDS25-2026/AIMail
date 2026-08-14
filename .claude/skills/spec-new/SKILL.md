---
name: spec-new
description: Use when starting a new feature in AImail. Scaffolds the spec-first workflow - copies the spec template, drafts a Goal and testable acceptance criteria from the user's description, and creates the feature branch. Invoke BEFORE writing any feature code.
---

Follow AImail's spec-first workflow. Do NOT write feature code until the spec exists.

1. Establish (ask or infer): the feature name (kebab-case), which lane it belongs to, and a one-line goal.
2. Copy `specs/_template.md` to `specs/features/<name>.md`.
3. Fill in Goal, User story, Scope (in/out), and **testable** Acceptance criteria in Given/When/Then form. Each AC must be observable and checkable - if you cannot imagine writing a test for it, sharpen it.
4. Note Dependencies and any cross-lane seams. Flag explicitly if it touches another lane's folder or a shared contract (`specs/context/`).
5. Create the branch: `git switch main && git pull && git switch -c feat/<name>`.
6. Show the spec for review before any implementation. If a design choice was made, also log it via the `log-decision` skill.
