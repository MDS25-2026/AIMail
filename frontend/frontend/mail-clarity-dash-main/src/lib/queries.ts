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

import { addDocument, fetchDocuments, fetchEmails, fetchSystemInfo, uploadDocument } from "./api";

export const queryKeys = {
  emails: ["emails"] as const,
  documents: ["documents"] as const,
  systemInfo: ["system-info"] as const,
};

export function useEmails() {
  return useQuery({ queryKey: queryKeys.emails, queryFn: fetchEmails });
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
