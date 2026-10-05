/**
 * Per-browser display preferences: theme, language, unit system.
 *
 * Kept in cookies rather than localStorage because the page is server-rendered: the server must
 * know the theme and language to render the right <html> on the first paint, or the reader sees
 * a flash of the wrong one and React sees a hydration mismatch. None of these is sensitive.
 */

export enum Theme {
  Light = "light",
  Dark = "dark",
  System = "system",
}

export enum Language {
  English = "en",
  Malay = "ms",
  Chinese = "zh",
}

export enum UnitSystem {
  Metric = "metric",
  Imperial = "imperial",
}

export type Preferences = { theme: Theme; language: Language; units: UnitSystem };

export const DEFAULT_PREFERENCES: Preferences = {
  theme: Theme.System,
  language: Language.English,
  units: UnitSystem.Metric,
};

export const COOKIE = {
  theme: "aimail-theme",
  language: "aimail-lang",
  units: "aimail-units",
} as const;

const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

function oneOf<T extends string>(
  values: Record<string, T>,
  raw: string | undefined,
  fallback: T,
): T {
  const allowed: string[] = Object.values(values);
  return raw !== undefined && allowed.includes(raw) ? (raw as T) : fallback;
}

/** A cookie value is untrusted input: anything unrecognised falls back to the default. */
export function parsePreferences(read: (name: string) => string | undefined): Preferences {
  return {
    theme: oneOf(Theme, read(COOKIE.theme), DEFAULT_PREFERENCES.theme),
    language: oneOf(Language, read(COOKIE.language), DEFAULT_PREFERENCES.language),
    units: oneOf(UnitSystem, read(COOKIE.units), DEFAULT_PREFERENCES.units),
  };
}

export function writePreference(name: string, value: string): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${ONE_YEAR_SECONDS}; samesite=lax`;
}

/**
 * Applies a "system" theme before first paint. The server cannot see the OS setting, so for
 * that one case a tiny inline script adds the class; Light and Dark are rendered server-side.
 */
export const SYSTEM_THEME_SCRIPT = `(function(){try{if(window.matchMedia("(prefers-color-scheme: dark)").matches){document.documentElement.classList.add("dark")}}catch(e){}})();`;
