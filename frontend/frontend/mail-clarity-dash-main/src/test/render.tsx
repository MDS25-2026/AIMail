import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { cleanup, render, renderHook } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { I18nextProvider } from "react-i18next";
import { afterEach, vi } from "vitest";

import { createI18n } from "../lib/i18n";
import { DEFAULT_PREFERENCES, Language } from "../lib/preferences";
import { createQueryClient } from "../lib/queries";
import { PreferencesContext, type PreferencesContextValue } from "../lib/usePreferences";

// No vitest globals here, so Testing Library cannot register its own cleanup.
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const noop = () => undefined;
const PREFERENCES: PreferencesContextValue = {
  preferences: DEFAULT_PREFERENCES,
  setTheme: noop,
  setLanguage: noop,
  setUnits: noop,
  setColours: noop,
};

/** The app's query client, minus retries, so a failing call shows its error at once. */
export function testQueryClient(): QueryClient {
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false }, mutations: { retry: false } });
  return client;
}

function providers(client: QueryClient) {
  const i18n = createI18n(Language.English);
  return function Providers({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <PreferencesContext.Provider value={PREFERENCES}>
          <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
        </PreferencesContext.Provider>
      </QueryClientProvider>
    );
  };
}

/** Renders inside the same providers as the app: query client, preferences, English i18n. */
export function renderWithProviders(ui: ReactElement, client = testQueryClient()) {
  return { ...render(ui, { wrapper: providers(client) }), client };
}

export function renderHookWithProviders<Props, Result>(
  hook: (props: Props) => Result,
  options: { initialProps?: Props; client?: QueryClient } = {},
) {
  const client = options.client ?? testQueryClient();
  const rendered = renderHook(hook, {
    wrapper: providers(client),
    initialProps: options.initialProps,
  });
  return { ...rendered, client };
}
