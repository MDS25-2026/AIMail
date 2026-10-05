import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";

import { SignedOutError } from "../lib/api";
import { createI18n } from "../lib/i18n";
import { Language, Theme, UnitSystem, type Preferences } from "../lib/preferences";
import { PreferencesContext, type PreferencesContextValue } from "../lib/usePreferences";

const DARK_QUERY = "(prefers-color-scheme: dark)";
const MAX_RETRIES = 3;
const LANGUAGE_BY_PREFIX: Record<string, Language> = { ms: Language.Malay, zh: Language.Chinese };

/** The panel has no settings page: it speaks the browser's language and follows the OS theme. */
function browserLanguage(): Language {
  return LANGUAGE_BY_PREFIX[navigator.language.slice(0, 2)] ?? Language.English;
}

function useSystemTheme(): void {
  useEffect(() => {
    const media = window.matchMedia(DARK_QUERY);
    const apply = () => document.documentElement.classList.toggle("dark", media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
}

export default function ExtensionProviders({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState<Preferences>(() => ({
    theme: Theme.System,
    language: browserLanguage(),
    units: UnitSystem.Metric,
  }));
  const i18n = useMemo(() => createI18n(preferences.language), []); // eslint-disable-line react-hooks/exhaustive-deps
  const queryClient = useMemo(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (failures, error) =>
              !(error instanceof SignedOutError) && failures < MAX_RETRIES,
          },
        },
      }),
    [],
  );
  useSystemTheme();

  const value = useMemo<PreferencesContextValue>(
    () => ({
      preferences,
      setTheme: (theme) => setPreferences((current) => ({ ...current, theme })),
      setLanguage: (language) => {
        void i18n.changeLanguage(language);
        setPreferences((current) => ({ ...current, language }));
      },
      setUnits: (units) => setPreferences((current) => ({ ...current, units })),
    }),
    [preferences, i18n],
  );

  return (
    <QueryClientProvider client={queryClient}>
      <PreferencesContext.Provider value={value}>
        <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
      </PreferencesContext.Provider>
    </QueryClientProvider>
  );
}
