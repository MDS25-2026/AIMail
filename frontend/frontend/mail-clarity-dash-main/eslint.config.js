import js from "@eslint/js";
import eslintPluginPrettier from "eslint-plugin-prettier/recommended";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

const SERVER_ONLY = {
  name: "server-only",
  message:
    "TanStack Start does not use the Next.js `server-only` package. Rename the module to `*.server.ts` or mark it with `@tanstack/react-start/server-only`.",
};
const REACT_QUERY = {
  name: "@tanstack/react-query",
  message: "Use the hooks in src/lib/queries; only the data layer and the providers use React Query.",
};
// Fetchers and cache keys stay behind the hooks; types, config and errors may be imported anywhere.
const FETCHERS = {
  group: [
    "**/lib/api/client",
    "**/lib/api/session",
    "**/lib/api/emails",
    "**/lib/api/documents",
    "**/lib/api/settings",
    "**/lib/api/profile",
    "**/lib/api/audit",
    "**/lib/queries/*",
  ],
  allowTypeImports: true,
  message: "Components get data through the hooks exported from src/lib/queries.",
};
const restrictImports = (options) => ({
  "no-restricted-imports": "off",
  "@typescript-eslint/no-restricted-imports": ["error", options],
});

export default tseslint.config(
  { ignores: ["dist", ".output", ".vinxi", "extension-dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      ...restrictImports({ paths: [SERVER_ONLY, REACT_QUERY] }),
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
  {
    files: ["src/components/**/*.tsx", "src/routes/**/*.tsx", "src/extension/**/*.{ts,tsx}"],
    rules: restrictImports({ paths: [SERVER_ONLY, REACT_QUERY], patterns: [FETCHERS] }),
  },
  {
    // The data layer itself, the two providers that hand it a client, and the test harness.
    files: [
      "src/lib/queries/**/*.ts",
      "src/router.tsx",
      "src/routes/__root.tsx",
      "src/extension/ExtensionProviders.tsx",
      "src/test/**/*.{ts,tsx}",
    ],
    rules: restrictImports({ paths: [SERVER_ONLY] }),
  },
  {
    // TanStack file routes export `Route` beside their components by design, and the router
    // plugin handles hot reload for them; vendored shadcn/ui exports its variant helpers the same
    // way. The rule cannot see either pattern, so it is off for exactly those folders.
    files: ["src/routes/**/*.tsx", "src/components/ui/**/*.tsx"],
    rules: { "react-refresh/only-export-components": "off" },
  },
  eslintPluginPrettier,
);
