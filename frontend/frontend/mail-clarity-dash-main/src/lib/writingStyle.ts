import type { TFunction } from "i18next";

import { WritingStyleError } from "./api";

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
