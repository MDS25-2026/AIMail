import type { SessionInfo } from "../../types/session";
import { HttpMethod, request } from "./client";

/** Who is signed in, and whether a mailbox is connected to that account. */
export const fetchSession = () => request<SessionInfo>("/auth/session");

/** End the session at Supabase and clear the cookies. */
export const signOut = () => request<void>("/auth/session", { method: HttpMethod.Delete });

/** Stop AIMail reading the reader's Gmail and delete what it stored from it (Settings > Account). */
export const disconnectGmail = () => request<void>("/account/gmail", { method: HttpMethod.Delete });

/** Delete everything the reader has in AIMail, then their sign-in. Safe to try again. */
export const deleteAccount = () => request<void>("/account", { method: HttpMethod.Delete });
