# Plan: iMail Chrome extension that runs on Gmail

## Goal

Ship a self-contained Manifest V3 Chrome extension that injects the existing `ExtensionPanel` (React + Tailwind, mock data) into gmail.com pages — no dependency on the hosted app.

## What gets built

### 1. Extension source — `extension/`

```text
extension/
├── manifest.json          MV3, content script on *://mail.google.com/*
├── content-entry.tsx      Mounts ExtensionPanel into a Shadow DOM root
├── content.css            Minimal preflight-safe styles for the shadow root
├── toggle button          Small "iMail" launcher injected into Gmail
└── icon.png               Toolbar/extension icon (generated)
```

- `manifest.json`: MV3, `content_scripts` matching `https://mail.google.com/*`, plus `action` icon. No host permissions beyond Gmail. No background worker needed (mock data, no messaging yet).
- `content-entry.tsx`: imports the existing `src/components/extension/*` components and `src/mockData/emails.ts`, renders `ExtensionPanel` with local `useState` (selected email, draft, tone, isRegenerating/isRefining with the same 500-800ms stubs). Wires `onRegenerate` / `onRefine` / `onApproveSend` to the same stubbed handlers used in the preview.
- **Shadow DOM mount**: the panel renders inside a shadow root so Gmail's CSS can't leak in and ours can't leak out. Computed Tailwind CSS is inlined into the shadow root at build time.
- A small floating "iMail" button toggles the 380px panel open/closed on the right edge of the Gmail page.

### 2. Build pipeline — `extension/vite.config.ts` + script

- Separate minimal Vite build (not the app's) that bundles `content-entry.tsx` to a single `content.js` with React inlined, and emits the collected CSS as a string the entry injects into the shadow root (or a `content.css` listed in the manifest).
- `bun run build:extension` script added to `package.json`: builds into `extension/dist/`, copies `manifest.json` + icon, then zips to `public/imail-extension.zip` using the nix zip workaround.

### 3. Download + install instructions in the dashboard

- Add a small "Get the Chrome extension" card (dashboard or `/extension-preview`) with a fetch+blob download of `/imail-extension.zip` (direct `<a download>` fails in preview) and the 4 install steps (unzip → `chrome://extensions` → Developer mode → Load unpacked).

## Verification

- Build the extension bundle and confirm it emits without errors.
- Zip lands in `public/imail-extension.zip`.
- Load the unpacked extension into sandbox Chromium via Playwright, open a page, and confirm the content script mounts and the panel renders/toggles (Gmail itself requires login, so mount verification may use the content-script match logic against a test page; will report exactly what was verified).
- Confirm the dashboard and `/extension-preview` still build and render unchanged.

## Out of scope (this pass)

- Reading real Gmail thread data (DOM scraping) — later pass.
- Real AI calls from the extension — handlers stay stubbed.
- Chrome Web Store publishing — install is via Load unpacked.

## Technical notes

- MV3 `content_scripts` with `run_at: "document_idle"`; CSS isolated via shadow root.
- The extension build reuses `src/components/extension/` and `src/mockData/emails.ts` directly — the portability work already done means no component changes are needed.
- No `localStorage`, no routing, no context in the content script — matches the existing portability constraints.
