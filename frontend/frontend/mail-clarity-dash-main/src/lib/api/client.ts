import { BACKEND_URL } from "./config";
import { ApiError, ApiErrorCode, apiErrorFrom } from "./errors";

export enum HttpMethod {
  Get = "GET",
  Post = "POST",
  Put = "PUT",
  Delete = "DELETE",
}

/** `json` is sent as a JSON body; `form` as multipart, whose boundary the browser sets itself. */
export type RequestOptions = { method?: HttpMethod; json?: object; form?: FormData };

// The backend refuses a cookie request that changes state without it (CSRF, ADR 0005).
const CLIENT_HEADER = { "X-AIMail-Client": "1" };
const JSON_HEADERS = { ...CLIENT_HEADER, "Content-Type": "application/json" };
const UNAUTHORIZED = 401;
const NO_RESPONSE = 0;

function send(path: string, options: RequestOptions): Promise<Response> {
  return fetch(`${BACKEND_URL}${path}`, {
    method: options.method ?? HttpMethod.Get,
    credentials: "include",
    headers: options.json ? JSON_HEADERS : CLIENT_HEADER,
    body: options.json ? JSON.stringify(options.json) : options.form,
  });
}

async function sendOrThrow(
  path: string,
  options: RequestOptions,
  endpoint: string,
): Promise<Response> {
  try {
    return await send(path, options);
  } catch (cause) {
    throw new ApiError(NO_RESPONSE, ApiErrorCode.Network, endpoint, { cause });
  }
}

// Shared by every call that finds the session expired at once: a refresh token can be spent only
// once, so a second, parallel renewal would be refused and sign the reader out.
let renewing: Promise<boolean> | null = null;

/** Trade the refresh cookie for a new session (the access cookie lasts an hour, this one a week). */
function renewSession(): Promise<boolean> {
  renewing ??= send("/auth/session/refresh", { method: HttpMethod.Post })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      renewing = null;
    });
  return renewing;
}

const signedOut = (endpoint: string) =>
  new ApiError(UNAUTHORIZED, ApiErrorCode.SignedOut, endpoint);

/** An expired session is renewed once and the call retried; only then is the reader signed out. */
async function sendSignedIn(
  path: string,
  options: RequestOptions,
  endpoint: string,
): Promise<Response> {
  const res = await sendOrThrow(path, options, endpoint);
  if (res.status !== UNAUTHORIZED) return res;
  if (!(await renewSession())) throw signedOut(endpoint);
  const retried = await sendOrThrow(path, options, endpoint);
  if (retried.status === UNAUTHORIZED) throw signedOut(endpoint);
  return retried;
}

// The validation boundary: the backend's response models are the contract for these shapes.
async function readBody(res: Response) {
  const text = await res.text();
  return text ? JSON.parse(text) : undefined;
}

/** Every dashboard call: the HttpOnly session cookie, never a token, and one ApiError on failure. */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const endpoint = `${options.method ?? HttpMethod.Get} ${path.split("?")[0]}`;
  const res = await sendSignedIn(path, options, endpoint);
  if (!res.ok) throw await apiErrorFrom(res, endpoint);
  return readBody(res);
}
