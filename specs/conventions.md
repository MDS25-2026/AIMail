# Conventions

Code style and naming rules for AImail. Read this before writing code.

## Python (`backend/`, early `listener/`)

- **Style:** [PEP 8](https://peps.python.org/pep-0008/).
- **Formatter:** `black` (line length 100). **Linter:** `ruff`.
- **Type hints required** on every function signature and return type. No bare `Any` outside validation boundaries.
- **Naming:**
  - Functions, variables, modules → `snake_case`
  - Classes, Pydantic models → `PascalCase`
  - Constants → `UPPER_SNAKE_CASE`
- **Imports:** absolute, grouped stdlib / third-party / local.
- **Errors:** typed exceptions; chain with `raise NewError(...) from original`. Never swallow.
- **Async:** prefer async I/O for FastAPI handlers; never block the event loop.

## TypeScript (`frontend/`)

- **No plain JS.** `.ts` and `.tsx` only.
- **Linter:** ESLint (Next.js config). **Formatter:** Prettier.
- **Naming:**
  - Variables, functions, hooks → `camelCase` (`useThreadList`)
  - Components, types, interfaces → `PascalCase` (`ThreadCard`, `Draft`)
  - Constants → `UPPER_SNAKE_CASE`
  - Files: components `PascalCase.tsx`, everything else `kebab-case.ts`
- **Booleans:** prefix with `is` / `has` / `can` / `should` / `was` / `will`.
- **No `any`.** Use `unknown` only at validation boundaries.
- **State:** prefer server components and React Query / TanStack Query for data; reach for client state only when justified.

## Go (`listener/go/`, future)

- **Format:** `gofmt` / `goimports`. Non-negotiable.
- **Linter:** `golangci-lint` (default ruleset).
- **Naming:** standard Go — exported `PascalCase`, unexported `camelCase`. Receiver names short and consistent.
- **Errors:** wrap with `fmt.Errorf("context: %w", err)`. Never discard.

## Filenames

- Markdown docs → `kebab-case.md` (e.g. `pii-masking.md`).
- Code files → language convention (above).
- One feature spec per file in `specs/features/`.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/). See [`../CONTRIBUTING.md`](../CONTRIBUTING.md).

## Comments

- Explain **why**, not **what**. The code already says what.
- Skip restating the signature, marking boilerplate, or narrating the next line.
- Good triggers: hidden constraint, non-obvious invariant, workaround for a specific bug (link the issue), unit assumed.
