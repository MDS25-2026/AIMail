/**
 * Builds the Chrome extension (specs/features/chrome-extension.md) into extension-dist/, separately
 * from the dashboard, whose TanStack Start build cannot produce extension pages. Two passes, since a
 * content script must be one classic script while the panel and worker share module chunks:
 *   vite build --config vite.extension.config.ts                 panel, worker, manifest, icons
 *   vite build --config vite.extension.config.ts --mode content  content.js (IIFE)
 */
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";

const CONTENT_MODE = "content";
const ENV_DIR = "../../..";
const EXTENSION_VERSION = "0.1.0";
// Matches src/lib/api.ts, so the panel and its host permission always name the same backend.
const DEFAULT_BACKEND_URL = "http://localhost:8000";
const GMAIL_MATCH = "https://mail.google.com/*";

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url));

function manifest(backendUrl: string): Plugin {
  return {
    name: "aimail-extension-manifest",
    generateBundle() {
      const icons = { 16: "icons/icon-16.png", 48: "icons/icon-48.png", 128: "icons/icon-128.png" };
      const body = {
        manifest_version: 3,
        name: "AIMail",
        version: EXTENSION_VERSION,
        description: "Private email assistant beside Gmail: summaries and approved replies.",
        icons,
        action: { default_title: "AIMail", default_icon: icons },
        side_panel: { default_path: "sidepanel.html" },
        background: { service_worker: "background.js", type: "module" },
        content_scripts: [{ matches: [GMAIL_MATCH], js: ["content.js"], run_at: "document_idle" }],
        permissions: ["sidePanel"],
        host_permissions: [GMAIL_MATCH, `${new URL(backendUrl).origin}/*`],
      };
      this.emitFile({
        type: "asset",
        fileName: "manifest.json",
        source: JSON.stringify(body, null, 2),
      });
    },
  };
}

export default defineConfig(({ mode }) => {
  const backendUrl = loadEnv(mode, here(ENV_DIR), "VITE_").VITE_BACKEND_URL || DEFAULT_BACKEND_URL;
  const shared = {
    root: here("./src/extension"),
    envDir: here(ENV_DIR),
    resolve: { alias: { "@": here("./src") } },
    plugins: [react(), tailwindcss()],
  };
  if (mode === CONTENT_MODE) {
    return {
      ...shared,
      publicDir: false,
      build: {
        outDir: here("./extension-dist"),
        emptyOutDir: false,
        rollupOptions: {
          input: here("./src/extension/content.ts"),
          output: { format: "iife", entryFileNames: "content.js" },
        },
      },
    };
  }
  return {
    ...shared,
    publicDir: here("./extension-public"),
    plugins: [...shared.plugins, manifest(backendUrl)],
    build: {
      outDir: here("./extension-dist"),
      emptyOutDir: true,
      rollupOptions: {
        input: {
          sidepanel: here("./src/extension/sidepanel.html"),
          background: here("./src/extension/background.ts"),
        },
        output: {
          entryFileNames: "[name].js",
          chunkFileNames: "chunks/[name]-[hash].js",
          assetFileNames: "assets/[name]-[hash][extname]",
        },
      },
    },
  };
});
