import { Language } from "./preferences";
import type { TemplateDraft } from "../types/template";

// Mirror backend/app/core/constants.py; the backend refuses anything longer.
export const MAX_TEMPLATE_TITLE_CHARS = 120;
export const MAX_TEMPLATE_BODY_CHARS = 5_000;
export const MAX_TEMPLATE_TRIGGERS = 10;

export const LANGUAGES = [Language.English, Language.Malay, Language.Chinese] as const;

/** Each language's words for the variables AIMail fills; mirrors backend/app/templates.py. */
export const VARIABLE_WORDS: Record<Language, { name: string; myName: string; today: string }> = {
  [Language.English]: { name: "name", myName: "my name", today: "today" },
  [Language.Malay]: { name: "nama", myName: "nama saya", today: "hari ini" },
  [Language.Chinese]: { name: "名字", myName: "我的名字", today: "今天" },
};

export function emptyTemplate(language: Language): TemplateDraft {
  return { title: "", body: "", language, triggerKeywords: [] };
}

/** "invoice, bayar" -> ["invoice", "bayar"]: trimmed, blanks dropped, capped at the backend's limit. */
export function parseTriggers(text: string): string[] {
  return text
    .split(/[,，]/)
    .map((word) => word.trim())
    .filter(Boolean)
    .slice(0, MAX_TEMPLATE_TRIGGERS);
}
