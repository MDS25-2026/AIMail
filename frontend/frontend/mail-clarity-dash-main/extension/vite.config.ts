import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import tsconfigPaths from "vite-tsconfig-paths";

/**
 * Standalone build for the Chrome extension content script. Completely
 * separate from the TanStack Start app build: it bundles
 * extension/content-entry.tsx (plus the shared src/components/extension/*
 * components and mock data) into a single IIFE content.js.
 */
export default defineConfig({
  plugins: [react(), tailwindcss(), tsconfigPaths()],
  publicDir: false,
  define: {
    "process.env.NODE_ENV": JSON.stringify("production"),
    "process.env": "{}",
  },
  build: {
    // Inline images as data URLs so content.js stays a single self-contained file.
    assetsInlineLimit: 512 * 1024,
    outDir: "extension/dist",
    emptyOutDir: true,
    lib: {
      entry: "extension/content-entry.tsx",
      formats: ["iife"],
      name: "IMailContentScript",
      fileName: () => "content.js",
    },
    rollupOptions: {
      output: { inlineDynamicImports: true },
    },
  },
});
