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

import {
  addDocument,
  fetchDocuments,
  fetchEmail,
  fetchEmails,
  fetchSystemInfo,
  refineEmail,
  regenerateEmail,
  sendEmail,
  uploadDocument,
} from "./api";
import type { Email, Tone } from "../types/email";

export const queryKeys = {
  emails: ["emails"] as const,
  email: (id: string) => ["email", id] as const,
  documents: ["documents"] as const,
  systemInfo: ["system-info"] as const,
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
  return useQuery({
    queryKey: queryKeys.email(emailId ?? ""),
    queryFn: () => fetchEmail(emailId as string),
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
