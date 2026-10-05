# Mail AI Assistant

Build "iMail" dashboard and Chrome extension panel as plain React functional components 

with Tailwind CSS utility classes only (no shadcn, no component libraries) — this code is 

meant to be adapted into a team codebase, not just demoed, so keep it simple, readable, 

and conventionally structured.

STRUCTURE

Separate mock data from components:

 - /mockData — sample email objects, kept in one file, matching the data shape below

 - /components — presentational components only, no data generation inside them

DATA SHAPE (this is the contract the components should expect as props — treat it as 

the interface the rest of the pipeline will eventually fill in for real):

Email = {

  id, sender, subject, preview, timestamp, priority ("high"|"medium"|"low"),

  threadContext: [ { sender, snippet } ],

  aiSummary: string,

  actionItems: [ string ],

  draftReply: string,

  tone: "professional" | "casual",

  sources: [ { label } ],

  piiMasked: boolean,

  criticConfidence: number  // 0-1, from the Critic Agent

}

COMPONENTS

 - InboxList / EmailListItem — renders the email list with priority badges

 - EmailDetailPanel — composes AISummaryCard, ActionItemsList, DraftReplyEditor, 

   SourcesChips, RefineInput

 - ToneToggle — Professional/Casual switch, controlled component

 - ApproveSendButton — takes an onApproveSend(emailId) callback prop (stub with 

   console.log for now) — this must be the only path that "sends," and should be 

   visually and functionally distinct from Regenerate/Refine actions

 - ExtensionPanel — reuses the same child components in a condensed layout, doesn't 

   duplicate their logic

 - DraftStatus + lib/useDraftWorkflow — regenerate, refine and send for both the inbox and

   the extension panel: asks before a regenerate replaces typed edits, warns before a reply

   containing a redaction marker is sent, and keeps failures on screen

BEHAVIOR

 - Selecting an email in InboxList updates EmailDetailPanel via props/state, not global 

   state library — keep it simple (useState/lift state up is fine)

 - Regenerate and refine-with-AI actions should be stubbed functions clearly named so 

   they're easy to wire to a real API later (e.g. onRegenerate, onRefine)

 - criticConfidence and piiMasked should be displayed as small indicators (e.g. a badge 

   or icon), since these map to actual project goals (80% critic confidence, PII masking 

   accuracy) and may get asked about later

STYLE

Clean corporate SaaS aesthetic, neutral grays/blues. Prioritize readable component code 

over visual polish — this needs to be easy for teammates to read and extend.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/89e8a0c8-d59d-4141-b1ce-ccd6a2b209c1).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```

## Chrome extension

The side panel beside Gmail (`specs/features/chrome-extension.md`). Source in `src/extension/`;
the panel itself is `src/components/SidePanel.tsx`, which the dashboard's `/extension` page also
renders. Built separately from the dashboard, with no extra dependencies:

```sh
make extension     # from the repo root: extension-dist/ plus aimail-extension.zip
```

Install (each tester, about a minute): unzip `aimail-extension.zip`, open `chrome://extensions`,
turn on **Developer mode**, click **Load unpacked**, and choose the unzipped folder. Then sign in
once in the dashboard with the Google account used in Gmail, open Gmail, and click the AIMail icon.

- The backend address comes from `VITE_BACKEND_URL` in the repo-root `.env` at build time (it also
  sets the extension's host permission), so rebuild after changing it.
- The panel uses the dashboard's session cookie; nothing is stored in the extension.
- A Gmail tab opened before installing needs one reload.
- Icons: `extension-public/icons/`, drawn by `scripts/make-extension-icons.py`.

## Colours, themes and languages

- **Never use raw Tailwind colours** (`bg-white`, `text-slate-700`, `bg-red-50`). Use the semantic
  classes: `bg-app`, `bg-surface`, `bg-surface-muted`, `text-fg`, `text-fg-body`, `text-fg-muted`,
  `text-fg-subtle`, `border-line`, `bg-brand` / `text-on-brand`, and for status `success`,
  `warning`, `danger`, `info` (each with `-soft` and `-line`). Dark mode is then one class on
  `<html>` and needs nothing per component.
- **Colours live in `scripts/palette.json`.** True-grey neutrals with dark-grey text and one navy
  accent. Status colours come in two sets that readers choose in Settings (the extension's eye
  button keeps its own copy): the standard green, amber and red, and a colour-blind friendly set
  applied by `data-colours="friendly"` on `<html>`. `python3 scripts/check-palette.py` verifies
  WCAG 2.1 contrast for both sets in both themes, and that the friendly set stays distinguishable
  under protan, deutan and tritan colour blindness; `--write` regenerates `src/palette.css`. Never
  edit that file by hand, and do not run Prettier over it.
- **Status never rests on colour alone** (WCAG 1.4.1): pair it with an icon and words.
- **Every visible string comes from `src/locales/`** via `useTranslation()`. `en.ts` is the master;
  `ms.ts` and `zh.ts` are typed against it, so a missing key fails `tsc`. Malay and Chinese need a
  native reviewer before release.
- Theme, language and unit system are cookies (`src/lib/preferences.ts`), read on the server so the
  first paint is already right. The reader changes them in Settings.
