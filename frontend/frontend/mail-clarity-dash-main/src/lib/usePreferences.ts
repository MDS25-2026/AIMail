import { createContext, useContext } from "react";

import type { Language, Preferences, StatusColours, Theme, UnitSystem } from "./preferences";

export type PreferencesContextValue = {
  preferences: Preferences;
  setTheme: (theme: Theme) => void;
  setLanguage: (language: Language) => void;
  setUnits: (units: UnitSystem) => void;
  setColours: (colours: StatusColours) => void;
};

export const PreferencesContext = createContext<PreferencesContextValue | null>(null);

export function usePreferences(): PreferencesContextValue {
  const context = useContext(PreferencesContext);
  if (context === null) throw new Error("usePreferences must be used inside PreferencesProvider");
  return context;
}
