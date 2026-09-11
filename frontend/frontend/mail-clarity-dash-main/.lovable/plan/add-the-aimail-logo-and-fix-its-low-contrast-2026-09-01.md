# Add the AIMail logo (and fix its low contrast)

## The contrast problem

The uploaded mark is a pale mint-to-blue gradient "AI" with a light grey "mail" wordmark. On white it nearly disappears. Fix by never placing it directly on white:

- **Dark chip treatment (recommended).** Sit the logo on the existing dark navy (`slate-900`) rounded surface — same look as the pill in the earlier reference image. The gradient pops against navy and the grey "mail" reads as near-white.
- **Darken the wordmark part** where the logo appears on light surfaces: use a version where "mail" is `slate-900` instead of pale grey, keeping the gradient "AI" as-is. Produced as a second asset variant via image editing (no redraw, same shapes).

So: light surfaces get the dark-wordmark variant; the extension launcher and any dark surface get the original on navy.

## Where the logo goes

1. **Dashboard header** (circled area, `src/routes/index.tsx`) — logo image replaces the "AIMail" text, `alt="AIMail"`, ~24px tall, with "AI inbox assistant" kept beside it. Uses the dark-wordmark variant.
2. **Extension launcher button** (`extension/content-entry.tsx`) — the collapsed floating button in Gmail becomes the original logo on the navy pill, so clicking it to open the panel is instantly recognizable.
3. **Extension panel header** (`src/components/extension/ExtensionPanel.tsx`) — small logo replaces the blue dot + "AIMail" text, ~18px tall, dark-wordmark variant on the white header bar.
4. **Favicon** — derived from just the gradient "AI" glyph (the wordmark is unreadable at 16px), replacing the default Lovable icon in `public/`.
5. **Extension icon** (`extension/icon.png`) — same square "AI" glyph on navy, so the Chrome/Edge toolbar entry matches.

Nothing else is forced — the inbox rows, cards, and preview route stay text-only.

## Technical notes

- Upload the PNG once via `lovable-assets` to `src/assets/aimail-logo.png.asset.json`; create the dark-wordmark variant and the square glyph as separate assets/files.
- Extension code cannot use CDN-pointer imports at runtime the same way as the app bundle for the icon, so `extension/icon.png` stays a real file; the in-panel logo is inlined by the extension Vite build.
- Since the panel keeps a portable-component contract, the logo is imported inside `ExtensionPanel` only as a plain image src string — no routing/context dependency added.
- Rebuild `aimail-extension.zip` after the change so the download card ships the new branding.
