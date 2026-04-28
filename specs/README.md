# specs

This folder is the **source of truth** for what AImail does and how. Code follows specs, not the other way around.

## How it works

1. One feature = one file in [`features/`](features/).
2. Copy [`_template.md`](_template.md) when starting a new feature spec. Name it `kebab-case.md` (e.g. `pii-masking.md`).
3. Keep the **Status** field current: `draft` → `approved` → `in-progress` → `shipped` → `archived`.
4. AI agents (Claude Code, etc.) read the relevant spec **before** writing feature code. Humans do the same.
5. If reality diverges from the spec mid-implementation, update the spec in the same PR.

## Layout

```
specs/
├── README.md            # this file
├── _template.md         # copy this for new feature specs
├── architecture.md      # system architecture (4 components, flow)
├── conventions.md       # code style + naming
├── features/            # one .md per feature
└── context/
    ├── api-contracts.md # REST contract between backend ↔ frontend
    ├── db-schema.md     # Postgres schema source of truth
    └── tech-stack.md    # versions + doc links
```

## Rules

- No feature code without an approved spec.
- Specs ship as their own PR (no code), reviewed and merged before implementation begins. Exception: trivially small features may bundle spec + code in one PR if the reviewer is comfortable.
- Cross-cutting concerns (API shape, DB columns) live in `context/`, not duplicated per feature.
- Specs are short. If a spec exceeds two screens, split it.
