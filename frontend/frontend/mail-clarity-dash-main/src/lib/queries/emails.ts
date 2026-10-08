import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import type { Email, EmailPage, Tone } from "../../types/email";
import {
  confirmSender,
  fetchEmail,
  fetchEmailByThread,
  fetchEmailPage,
  refineEmail,
  regenerateEmail,
  sendEmail,
  translateEmail,
} from "../api/emails";
import { queryKeys } from "./keys";

// While the worker writes the first draft (email.isDrafting), the email is fetched again on this
// beat; it gives up after DRAFT_POLL_LIMIT tries (two minutes), when Regenerate is the way on.
export const DRAFT_POLL_MS = 3_000;
export const DRAFT_POLL_LIMIT = 40;

/** The inbox, page by page; `data` is every loaded email, newest first, and fetchNextPage loads older. */
export function useEmails() {
  return useInfiniteQuery({
    queryKey: queryKeys.emails,
    queryFn: ({ pageParam }) => fetchEmailPage(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.nextCursor ?? undefined,
    select: (data) => data.pages.flatMap((page) => page.emails),
  });
}

/**
 * One email with its Lane C draft. Idle until something is selected, and keyed by id, so a
 * response for a previously selected email lands in that email's entry, never the one on
 * screen. No refetch on focus: the call marks the email read and is rate limited.
 */
export function useEmail(emailId: string | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: queryKeys.email(emailId ?? ""),
    queryFn: async () => {
      const email = await fetchEmail(emailId ?? "");
      // Patch the cached list so the unread marker clears now, not at the next refetch.
      queryClient.setQueryData<InfiniteData<EmailPage>>(
        queryKeys.emails,
        (inbox) =>
          inbox && {
            ...inbox,
            pages: inbox.pages.map((page) => ({
              ...page,
              emails: page.emails.map((item) =>
                item.id === email.id ? { ...item, isRead: true } : item,
              ),
            })),
          },
      );
      return email;
    },
    enabled: emailId !== null,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      query.state.data?.isDrafting && query.state.dataUpdateCount < DRAFT_POLL_LIMIT
        ? DRAFT_POLL_MS
        : false,
  });
}

/** The extension's lookup of the open Gmail thread; null when AIMail has no email for it. */
export function useEmailByThread(threadId: string) {
  return useQuery({
    queryKey: queryKeys.emailByThread(threadId),
    queryFn: () => fetchEmailByThread(threadId),
  });
}

/** Seeded under the detail key so draft actions update it; never stale, a refetch regenerates. */
export function useSeededEmail(initial: Email) {
  return useQuery({
    queryKey: queryKeys.email(initial.id),
    queryFn: () => fetchEmail(initial.id),
    initialData: initial,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

/**
 * Keyed by email and language and never stale, so switching between original and translation
 * costs one model call. No retry: a 422 means the text failed its faithfulness checks.
 */
export function useEmailTranslation(emailId: string, language: string, isRequested: boolean) {
  return useQuery({
    queryKey: queryKeys.translation(emailId, language),
    queryFn: () => translateEmail(emailId, language),
    enabled: isRequested,
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * Every draft-mutating call returns the updated email, so the detail cache is written directly
 * rather than refetched (that endpoint re-runs generation). The list is invalidated instead,
 * which keeps Inbox and Sent consistent after a send.
 */
function useDraftMutation<TVariables>(mutationFn: (variables: TVariables) => Promise<Email>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.email(updated.id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
  });
}

export function useRegenerateEmail() {
  return useDraftMutation(({ emailId, tone }: { emailId: string; tone: Tone }) =>
    regenerateEmail(emailId, tone),
  );
}

type RefineVariables = { emailId: string; instruction: string; draft: string; tone: Tone };

export function useRefineEmail() {
  return useDraftMutation(({ emailId, instruction, draft, tone }: RefineVariables) =>
    refineEmail(emailId, instruction, draft, tone),
  );
}

/** A failure also refetches: an unknown outcome keeps the email claimed as sent. */
export function useSendEmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ emailId, draft }: { emailId: string; draft: string }) =>
      sendEmail(emailId, draft),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.email(updated.id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
    onError: (_error, { emailId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.email(emailId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
  });
}

export function useConfirmSender() {
  return useDraftMutation(confirmSender);
}
