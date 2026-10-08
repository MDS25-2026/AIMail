import type { ParseKeys, TFunction } from "i18next";

/** The backend's error codes (app/core/errors.py ErrorCode), plus the two the client adds. */
export enum ApiErrorCode {
  SenderUnverified = "sender_unverified",
  MaskingPending = "masking_pending",
  AlreadySent = "already_sent",
  RedactionMarkers = "redaction_markers",
  UnresolvedPlaceholders = "unresolved_placeholders",
  SendNotGranted = "send_not_granted",
  GoogleAccessExpired = "google_access_expired",
  SendFailed = "send_failed",
  SendOutcomeUnknown = "send_outcome_unknown",
  DraftRefused = "draft_refused",
  AgentUnavailable = "agent_unavailable",
  PrivateModeUnavailable = "private_mode_unavailable",
  MaskingUnavailable = "masking_unavailable",
  TooManyExamples = "too_many_examples",
  Empty = "empty",
  TooLong = "too_long",
  NotFound = "not_found",
  RateLimited = "rate_limited",
  TooLarge = "too_large",
  NotPdf = "not_pdf",
  SignedOut = "signed_out",
  // Holding-reply settings the backend refused (backend/app/holding_reply.py).
  UnknownPlaceholder = "unknown_placeholder",
  ReturnDateNeedsLeave = "return_date_needs_leave",
  EmptyTemplate = "empty_template",
  TemplateTooLong = "template_too_long",
  NoDefaultTemplate = "no_default_template",
  UnknownTimezone = "unknown_timezone",
  LeaveNeedsDates = "leave_needs_dates",
  LeaveEndsBeforeItStarts = "leave_ends_before_it_starts",
  WorkdayEndsBeforeItStarts = "workday_ends_before_it_starts",
  BadWorkDays = "bad_work_days",
  Invalid = "invalid",
  // Admin console sign-in (docs/adr/0004).
  InvalidCredentials = "invalid_credentials",
  NotAnAdmin = "not_an_admin",
  AdminAuthNotConfigured = "admin_auth_not_configured",
  SupabaseUnavailable = "supabase_unavailable",
  // Client-side: the request never reached the backend, or its answer named no code we know.
  Network = "network",
  Unknown = "unknown",
}

/** Every failed backend call. `message` is for logs only; the reader sees errorMessage(). */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: ApiErrorCode,
    readonly endpoint: string,
    options?: ErrorOptions,
  ) {
    super(`${endpoint} failed (${status}): ${code}`, options);
    this.name = "ApiError";
  }
}

export function isSignedOut(error: unknown): boolean {
  return error instanceof ApiError && error.code === ApiErrorCode.SignedOut;
}

const KNOWN_CODES: ReadonlySet<string> = new Set(Object.values(ApiErrorCode));

// Answers that carry no code, from proxies or older handlers, still say something by status.
const CODE_BY_STATUS: Readonly<Record<number, ApiErrorCode>> = {
  401: ApiErrorCode.SignedOut,
  404: ApiErrorCode.NotFound,
  413: ApiErrorCode.TooLarge,
  429: ApiErrorCode.RateLimited,
};

function isCode(raw: unknown): raw is ApiErrorCode {
  return typeof raw === "string" && KNOWN_CODES.has(raw);
}

function asCode(raw: unknown): ApiErrorCode | null {
  return isCode(raw) ? raw : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** The code in an error body: {"error":{"code"}} now, {"detail":"<code>"} until the backend moves. */
export function codeFromBody(body: unknown, status: number): ApiErrorCode {
  const envelope = isRecord(body) && isRecord(body.error) ? body.error.code : undefined;
  const legacy = isRecord(body) ? body.detail : undefined;
  return asCode(envelope) ?? asCode(legacy) ?? CODE_BY_STATUS[status] ?? ApiErrorCode.Unknown;
}

export async function apiErrorFrom(res: Response, endpoint: string): Promise<ApiError> {
  const body: unknown = await res.json().catch(() => null);
  return new ApiError(res.status, codeFromBody(body, res.status), endpoint);
}

/** What to tell the reader about a failure: the code's own message, else `fallback`. */
export function errorMessage(
  error: unknown,
  t: TFunction,
  fallback: ParseKeys = "errors.generic",
): string {
  const code = error instanceof ApiError ? error.code : ApiErrorCode.Unknown;
  if (code === ApiErrorCode.Unknown) return t(fallback);
  return t(`errors.${code}`);
}
