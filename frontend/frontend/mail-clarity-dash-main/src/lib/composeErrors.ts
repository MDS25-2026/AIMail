import type { ParseKeys, TFunction } from "i18next";

import { ApiError, ApiErrorCode, errorMessage } from "./api/errors";

// The codes whose shared wording speaks of a reply; a new email gets its own words for these.
const COMPOSE_WORDED = [
  ApiErrorCode.SendFailed,
  ApiErrorCode.AlreadySent,
  ApiErrorCode.SendInProgress,
  ApiErrorCode.SendOutcomeUnknown,
  ApiErrorCode.DraftRefused,
  ApiErrorCode.UnresolvedPlaceholders,
  ApiErrorCode.RedactionMarkers,
  ApiErrorCode.GoogleAccessExpired,
  ApiErrorCode.SendNotGranted,
  ApiErrorCode.Conflict,
] as const;
type ComposeWorded = (typeof COMPOSE_WORDED)[number];

function isComposeWorded(code: ApiErrorCode): code is ComposeWorded {
  return COMPOSE_WORDED.some((worded) => worded === code);
}

/** errorMessage() for a new email: its own wording where the shared one says "reply". */
export function composeErrorMessage(error: unknown, t: TFunction, fallback: ParseKeys): string {
  if (error instanceof ApiError && isComposeWorded(error.code)) {
    return t(`compose.errors.${error.code}`);
  }
  return errorMessage(error, t, fallback);
}
