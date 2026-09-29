# Lane D — Surfaces + evidence

- Owner: Tan Le Han (Han)
- Floor: usable + tested
- Covers: web dashboard, Chrome extension, eval harness, user testing
- Seams owned:
  - Consumes Lane B classifier output (priority display) and Lane C drafts (review UI).
  - Owns the full eval harness that measures every lane's models.

## Open flag (raise with team)

- ADR 0001 says "no chrome extension", but proposal R04.5 requires one (dual-interface).
  These contradict. Resolve before Lane D commits to a surface. Logged in
  [`shared.md`](shared.md).

## Log

_No entries yet. Add newest-first using the template in [`README.md`](README.md)._
### 2026-09-29 — Semantic colour tokens, a verified colour-blind-safe palette, three languages
- Decision: components use semantic colour classes (`bg-surface`, `text-fg-muted`, `text-danger`
  ...) generated from `scripts/palette.json`, never raw Tailwind colours; dark mode is the `dark`
  class on `<html>`. Every string comes from `src/locales/{en,ms,zh}.ts` through react-i18next.
  Theme, language and unit system are cookies read on the server.
- Why: 203 hardcoded colour classes made dark mode impossible without touching every component
  again, and the status pairs in use (emerald vs amber, emerald vs red) are exactly the ones
  red-green colour-blind readers cannot tell apart. `check-palette.py` measured it: the obvious
  orange/vermillion warning/danger pair collapsed to dE 1.2 under protanopia. Success and danger
  were then chosen by searching their hue families for the largest worst-case separation.
- Why cookies over localStorage: the page is server-rendered, so only a cookie lets the first
  paint carry the right theme and language, with no flash and no hydration mismatch.
- Why not a separate "colour-blind mode": a safe default serves readers who never find a setting.
- Affects: every component and route, `styles.css`, new `src/palette.css`, `src/locales/`,
  `src/lib/{preferences,i18n,highlight,useInboxKeyboard,useFormat}.ts`, `package.json`
  (i18next, react-i18next, both MIT, approved 2026-09-29).
- Status: implemented by veyroxie; needs Han's review as Lane D owner.

