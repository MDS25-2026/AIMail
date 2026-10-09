import type { Email, EmailPage, Tone, Translation } from "../../types/email";
import { HttpMethod, request } from "./client";
import { ApiError, ApiErrorCode } from "./errors";

const emailPath = (id: string, action = "") => `/emails/${encodeURIComponent(id)}${action}`;

/** One page of the inbox, newest first: Lane A fields and Lane B priority, no draft. */
export const fetchEmailPage = (cursor?: string) =>
  request<EmailPage>(cursor ? `/emails?cursor=${encodeURIComponent(cursor)}` : "/emails");

/** One email with the Lane C draft, summary and critic filled in. Marks it read. */
export const fetchEmail = (id: string, signal?: AbortSignal) =>
  request<Email>(emailPath(id), { signal });

/** The newest of the reader's emails in a Gmail thread, or null when AIMail has none (extension). */
export async function fetchEmailByThread(threadId: string): Promise<Email | null> {
  try {
    return await request<Email>(`/emails/by-thread/${encodeURIComponent(threadId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.code === ApiErrorCode.NotFound) return null;
    throw error;
  }
}

/** Force a fresh draft in the given tone, replacing the cached one. */
export const regenerateEmail = (id: string, tone: Tone) =>
  request<Email>(emailPath(id, "/regenerate"), { method: HttpMethod.Post, json: { tone } });

/** Revise the current draft per a user instruction. */
export const refineEmail = (id: string, instruction: string, draft: string, tone: Tone) =>
  request<Email>(emailPath(id, "/refine"), {
    method: HttpMethod.Post,
    json: { instruction, draft, tone },
  });

/** The masked body in another language. 422 means the translation failed its faithfulness checks. */
export const translateEmail = (id: string, language: string) =>
  request<Translation>(emailPath(id, "/translate"), {
    method: HttpMethod.Post,
    json: { language },
  });

/** Send the approved (possibly edited) draft as a reply; marks the email sent. */
export const sendEmail = (id: string, draft: string) =>
  request<Email>(emailPath(id, "/send"), { method: HttpMethod.Post, json: { draft } });

/** The owner checked a sender that failed SPF/DKIM/DMARC and says they are real; drafting resumes. */
export const confirmSender = (id: string) =>
  request<Email>(emailPath(id, "/confirm-sender"), { method: HttpMethod.Post });
