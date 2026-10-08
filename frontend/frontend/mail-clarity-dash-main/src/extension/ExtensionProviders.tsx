import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";

import { createI18n } from "../lib/i18n";
import { Language, StatusColours, Theme, UnitSystem, type Preferences } from "../lib/preferences";
import { createQueryClient } from "../lib/queries";
import { useColoursAttribute } from "../lib/useColoursAttribute";
import { PreferencesContext, type PreferencesContextValue } from "../lib/usePreferences";

const DARK_QUERY = "(prefers-color-scheme: dark)";
const LANGUAGE_BY_PREFIX: Record<string, Language> = { ms: Language.Malay, zh: Language.Chinese };
// The panel cannot read the dashboard's cookies, so it keeps its own copy of this one choice.
const COLOURS_KEY = "aimail-colours";

function storedColours(): StatusColours {
  try {
    return localStorage.getItem(COLOURS_KEY) === StatusColours.Friendly
      ? StatusColours.Friendly
      : StatusColours.Standard;
  } catch {
    return StatusColours.Standard; // storage blocked: the standard set
  }
}

function storeColours(colours: StatusColours): void {
  try {
    localStorage.setItem(COLOURS_KEY, colours);
  } catch {
    // Not remembered for next time; the choice still applies now.
  }
}

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
    colours: storedColours(),
  }));
  const i18n = useMemo(() => createI18n(preferences.language), []); // eslint-disable-line react-hooks/exhaustive-deps
  // No onSignedOut: each panel state already shows the sign-in button from its own error.
  const queryClient = useMemo(() => createQueryClient(), []);
  useSystemTheme();
  useColoursAttribute(preferences.colours);

  const value = useMemo<PreferencesContextValue>(
    () => ({
      preferences,
      setTheme: (theme) => setPreferences((current) => ({ ...current, theme })),
      setLanguage: (language) => {
        void i18n.changeLanguage(language);
        setPreferences((current) => ({ ...current, language }));
      },
      setUnits: (units) => setPreferences((current) => ({ ...current, units })),
      setColours: (colours) => {
        storeColours(colours);
        setPreferences((current) => ({ ...current, colours }));
      },
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
