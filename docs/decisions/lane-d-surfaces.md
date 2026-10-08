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
### 2026-09-30 — Draft actions no longer lose work or fail silently
- Decision: regenerate, refine and send go through one hook, `src/lib/useDraftWorkflow.ts`,
  used by both the inbox and the extension panel, with `DraftStatus` showing its state. A
  regenerate over typed edits asks first; a reply still containing a redaction marker
  (`[Redacted]`, `[EMAIL_REDACTED]`, ...) warns before sending; failures stay on screen; a failed
  refine keeps the instruction; the inbox has loading, error (with retry) and empty states; the
  draft shows "Writing a draft" and blocks sending until the first one lands.
- Why: a UX audit found edits silently replaced on tone change or regenerate, errors swallowed
  (the code said "the mutation's error state drives the UI", but nothing rendered it), a failed
  send shown as a browser `alert`, and "0 messages" while loading or when the backend was down.
  The extension panel had copied the page's logic and also let a send run mid-refine.
- Why state keyed by email id: a slow response for one email could otherwise clear the typed
  edits of the email opened since.
- The backend used to answer 200 with the unchanged draft when the agent failed; it now answers an
  error status (see `shared.md`, 2026-09-30), so those failures reach this message too.
- Affects: `routes/{index,extension}.tsx`, `components/{EmailDetailPanel,ExtensionPanel,
  DraftActionsBar,RefineInput,PageState,DraftStatus}.tsx`, `lib/{draftGuards,useDraftWorkflow}.ts`,
  `locales/{en,ms,zh}.ts` (new `draftStatus`, `inbox.empty*`, `page.retry`; `draft.sendFailed` removed).
- Status: implemented by veyroxie; reviewed and accepted by Han 2026-10-08. One gap found: the tone
  toggle was never disabled, so a tone change could regenerate the draft mid-send, and the draft
  stayed editable after sending. Fixed in #172.

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
- Status: implemented by veyroxie; reviewed and accepted by Han 2026-10-08 (no raw colour classes
  left outside `components/ui/`; the compiler keeps the three locales in step). New Lane D work
  follows the tokens and locales.

