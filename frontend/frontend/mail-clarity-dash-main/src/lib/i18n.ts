import i18next, { type i18n } from "i18next";
import { initReactI18next } from "react-i18next";

import { en } from "../locales/en";
import { ms } from "../locales/ms";
import { zh } from "../locales/zh";
import { Language } from "./preferences";

export const resources = {
  [Language.English]: { translation: en },
  [Language.Malay]: { translation: ms },
  [Language.Chinese]: { translation: zh },
} as const;

/**
 * One instance per render tree, never a shared global: on the server, concurrent requests in
 * different languages would otherwise switch each other's language mid-render. Resources are
 * bundled, so initialisation is synchronous and the first render is already translated.
 */
export function createI18n(language: Language): i18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources,
    lng: language,
    fallbackLng: Language.English,
    initAsync: false,
    // React already escapes rendered text; escaping again would show &amp; to the reader.
    interpolation: { escapeValue: false },
    returnNull: false,
  });
  return instance;
}
