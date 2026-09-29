/**
 * React Query layer for the dashboard.
 *
 * The QueryClientProvider has been wired in __root.tsx since the scaffold, but pages were
 * hand-rolling useState + useEffect + loading flags. Every page doing that reinvents caching,
 * refetching and error handling, and they drift apart. Fetching lives here instead: pages
 * declare what they need and render three states.
 *
 * `queryKeys` is the single place keys are defined, so an invalidation after a mutation can
 * never miss a cache entry because of a typo'd key.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  fetchAdminSession,
  fetchAudit,
  fetchFlagged,
  fetchOverview,
  isAuthError,
  retryUnlessAuth,
  signIn,
  signOut,
} from "./adminApi";
import {
  addDocument,
  fetchDocuments,
  fetchEmail,
  fetchEmails,
  fetchSystemInfo,
  refineEmail,
  regenerateEmail,
  sendEmail,
  translateEmail,
  uploadDocument,
} from "./api";
import type { Email, Tone } from "../types/email";

export const queryKeys = {
  emails: ["emails"] as const,
  email: (id: string) => ["email", id] as const,
  documents: ["documents"] as const,
  systemInfo: ["system-info"] as const,
  translation: (id: string, language: string) => ["translation", id, language] as const,
};

export function useEmails() {
  return useQuery({ queryKey: queryKeys.emails, queryFn: fetchEmails });
}

/**
 * One email with its Lane C draft. `enabled` keeps the query idle until something is selected,
 * and keying by id is what makes a stale response harmless: a reply for a previously selected
 * email lands in that email's cache entry, never in the one on screen.
 */
export function useEmail(emailId: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: queryKeys.email(emailId ?? ""),
    queryFn: async () => {
      const email = await fetchEmail(emailId as string);
      // Fetching the detail is what marks it read server-side. Patch the cached list so the
      // unread marker clears immediately rather than waiting for the next refetch.
      queryClient.setQueryData<Email[]>(queryKeys.emails, (list) =>
        list?.map((item) => (item.id === email.id ? { ...item, isRead: true } : item)),
      );
      return email;
    },
    enabled: emailId !== null,
  });
}

/**
 * Every draft-mutating call returns the updated email, so the detail cache is written directly
 * rather than refetched (that endpoint re-runs generation). The list is invalidated instead,
 * which is cheap and keeps Inbox, Drafts and Sent consistent after a send — the old manual
 * setState only patched the list the page was holding.
 */
function useDraftMutation<TVariables>(mutationFn: (variables: TVariables) => Promise<Email>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.email(updated.id), updated);
      queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
  });
}

/**
 * A translation is a query, not a mutation: keyed by email and language, and never stale, so
 * switching back and forth between original and translation costs one model call, not one per
 * click. Idle until the reader asks. No retry: a 422 means the text failed its faithfulness
 * checks, and asking again would only spend quota on the same refusal.
 */
export function useEmailTranslation(
  emailId: string | null,
  language: string,
  isRequested: boolean,
) {
  return useQuery({
    queryKey: queryKeys.translation(emailId ?? "", language),
    queryFn: () => translateEmail(emailId as string, language),
    enabled: emailId !== null && isRequested,
    staleTime: Infinity,
    retry: false,
  });
}

export function useRegenerateEmail() {
  return useDraftMutation<{ emailId: string; tone: Tone }>(({ emailId, tone }) =>
    regenerateEmail(emailId, tone),
  );
}

export function useRefineEmail() {
  return useDraftMutation<{ emailId: string; instruction: string; draft: string }>(
    ({ emailId, instruction, draft }) => refineEmail(emailId, instruction, draft),
  );
}

export function useSendEmail() {
  return useDraftMutation<{ emailId: string; draft: string }>(({ emailId, draft }) =>
    sendEmail(emailId, draft),
  );
}

export function useDocuments() {
  return useQuery({ queryKey: queryKeys.documents, queryFn: fetchDocuments });
}

export function useSystemInfo() {
  return useQuery({ queryKey: queryKeys.systemInfo, queryFn: fetchSystemInfo });
}

/** Both ingest paths invalidate the same two caches: the library grew, so the corpus stats did too. */
function useIngestMutation<TInput>(mutationFn: (input: TInput) => Promise<number>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.documents });
      queryClient.invalidateQueries({ queryKey: queryKeys.systemInfo });
    },
  });
}

export function useUploadDocument() {
  return useIngestMutation<File>(uploadDocument);
}

export function useAddDocument() {
  return useIngestMutation<{ title: string; text: string }>(({ title, text }) =>
    addDocument(title, text),
  );
}

// ---------- Admin console (docs/adr/0004) ----------

const adminKeys = {
  session: ["admin", "session"] as const,
  overview: (days: number) => ["admin", "overview", days] as const,
  flagged: ["admin", "flagged"] as const,
  audit: (failuresOnly: boolean) => ["admin", "audit", failuresOnly] as const,
};

/** Who is signed in to the console. A 401 is an answer ("nobody"), so it is not retried. */
export function useAdminSession() {
  return useQuery({ queryKey: adminKeys.session, queryFn: fetchAdminSession, retry: false });
}

export function useAdminOverview(days: number, isEnabled: boolean) {
  return useQuery({
    queryKey: adminKeys.overview(days),
    queryFn: () => fetchOverview(days),
    enabled: isEnabled,
    retry: retryUnlessAuth,
  });
}

export function useAdminFlagged(isEnabled: boolean) {
  return useQuery({
    queryKey: adminKeys.flagged,
    queryFn: fetchFlagged,
    enabled: isEnabled,
    retry: retryUnlessAuth,
  });
}

export function useAdminAudit(failuresOnly: boolean, isEnabled: boolean) {
  return useQuery({
    queryKey: adminKeys.audit(failuresOnly),
    queryFn: () => fetchAudit(failuresOnly),
    enabled: isEnabled,
    retry: retryUnlessAuth,
  });
}

export function useAdminSignIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      signIn(email, password),
    onSuccess: (identity) => queryClient.setQueryData(adminKeys.session, identity),
  });
}

/**
 * When any console panel finds the session gone (after its one refresh), ask again who is signed
 * in: the session query then fails too, and the page falls back to the sign-in form instead of
 * showing error panels.
 */
export function useSignedOutRecovery(errors: unknown[]): void {
  const queryClient = useQueryClient();
  const isSignedOut = errors.some(isAuthError);
  useEffect(() => {
    if (isSignedOut) void queryClient.invalidateQueries({ queryKey: adminKeys.session });
  }, [isSignedOut, queryClient]);
}

/** Signing out drops every admin query, so nothing from the session stays in the cache. */
export function useAdminSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signOut,
    onSettled: () => queryClient.removeQueries({ queryKey: ["admin"] }),
  });
}
