import type { TFunction } from "i18next";

import { WritingStyleError } from "./api";

// Mirrors backend/app/writing_style.py MAX_DESCRIPTION_CHARS.
export const MAX_DESCRIPTION_CHARS = 300;
export const WRITING_STYLE_KEY = ["writing-style"] as const;
// The codes the backend can send (backend/app/writing_style_routes.py, app/main.py).
const ERROR_CODES = ["masking_unavailable", "too_many_examples", "empty", "not_found"] as const;
type ErrorCode = (typeof ERROR_CODES)[number];
const isErrorCode = (code: string): code is ErrorCode =>
  (ERROR_CODES as readonly string[]).includes(code);

export function styleErrorText(error: Error | null, t: TFunction): string | null {
  if (error === null) return null;
  const code = error instanceof WritingStyleError ? error.code : "";
  return t(`writingStyle.errors.${isErrorCode(code) ? code : "failed"}`);
}

/** The description with `phrase` added, or taken out if it is already there. */
export function togglePhrase(text: string, phrase: string): string {
  if (text.includes(phrase))
    return text
      .replace(phrase, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  return [text.trim(), phrase].filter(Boolean).join(" ").slice(0, MAX_DESCRIPTION_CHARS);
}
