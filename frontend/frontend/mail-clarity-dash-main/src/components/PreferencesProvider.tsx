import { useRouter } from "@tanstack/react-router";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { I18nextProvider } from "react-i18next";

import { createI18n } from "../lib/i18n";
import { COOKIE, Theme, writePreference, type Preferences } from "../lib/preferences";
import { useColoursAttribute } from "../lib/useColoursAttribute";
import { PreferencesContext, type PreferencesContextValue } from "../lib/usePreferences";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function isDark(theme: Theme): boolean {
  if (theme === Theme.System) return window.matchMedia(DARK_QUERY).matches;
  return theme === Theme.Dark;
}

/** After hydration this effect is the one owner of the dark class, including live OS changes. */
function useThemeClass(theme: Theme): void {
  useEffect(() => {
    const apply = () => document.documentElement.classList.toggle("dark", isDark(theme));
    apply();
    if (theme !== Theme.System) return;
    const media = window.matchMedia(DARK_QUERY);
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [theme]);
}

export default function PreferencesProvider({
  initial,
  children,
}: {
  initial: Preferences;
  children: ReactNode;
}) {
  const router = useRouter();
  const [preferences, setPreferences] = useState(initial);
  // Created once per render tree; language changes go through changeLanguage on this instance.
  const i18n = useMemo(() => createI18n(initial.language), []); // eslint-disable-line react-hooks/exhaustive-deps
  useThemeClass(preferences.theme);
  useColoursAttribute(preferences.colours);

  const value = useMemo<PreferencesContextValue>(() => {
    const save = (next: Partial<Preferences>, cookie: string, stored: string) => {
      writePreference(cookie, stored);
      // Re-read the cookie in the root route first, then update state: the root re-render
      // rewrites <html class>, and the theme effect must run after it, not before, or switching
      // Dark to System on a dark OS would leave the page light.
      void router.invalidate().then(() => setPreferences((current) => ({ ...current, ...next })));
    };
    return {
      preferences,
      setTheme: (theme) => save({ theme }, COOKIE.theme, theme),
      setLanguage: (language) => {
        void i18n.changeLanguage(language);
        save({ language }, COOKIE.language, language);
      },
      setUnits: (units) => save({ units }, COOKIE.units, units),
      setColours: (colours) => save({ colours }, COOKIE.colours, colours),
    };
  }, [preferences, i18n, router]);

  return (
    <PreferencesContext.Provider value={value}>
      <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
    </PreferencesContext.Provider>
  );
}
