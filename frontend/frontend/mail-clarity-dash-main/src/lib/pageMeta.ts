import type { TFunction } from "i18next";

import { createI18n } from "./i18n";
import type { Language } from "./preferences";

/** Every page with its own title and description (locale `meta.*`). */
export enum Page {
  App = "app",
  Inbox = "inbox",
  Drafts = "drafts",
  Sent = "sent",
  Scheduled = "scheduled",
  Knowledge = "knowledge",
  Audit = "audit",
  Settings = "settings",
  Admin = "admin",
  Extension = "extension",
  SignIn = "signin",
}

// head() runs outside React; a cached translator per language is only read, so sharing it is safe.
const translators = new Map<Language, TFunction>();

function translatorFor(language: Language): TFunction {
  const cached = translators.get(language);
  if (cached) return cached;
  const { t } = createI18n(language);
  translators.set(language, t);
  return t;
}

export type MetaTag =
  { title: string } | { name: string; content: string } | { property: string; content: string };

/** The page's title and description in the reader's language, plus the matching Open Graph tags. */
export function pageMeta(language: Language, page: Page): MetaTag[] {
  const t = translatorFor(language);
  const title = t(`meta.${page}.title`);
  const description = t(`meta.${page}.description`);
  return [
    { title },
    { name: "description", content: description },
    { property: "og:title", content: title },
    { property: "og:description", content: description },
  ];
}
