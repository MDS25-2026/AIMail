import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Email, Tone } from "../../types/email";
import {
  confirmSender,
  fetchEmail,
  fetchEmailByThread,
  fetchEmails,
  refineEmail,
  regenerateEmail,
  sendEmail,
  translateEmail,
} from "../api/emails";
import { queryKeys } from "./keys";

export function useEmails() {
  return useQuery({ queryKey: queryKeys.emails, queryFn: fetchEmails });
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
      queryClient.setQueryData<Email[]>(queryKeys.emails, (list) =>
        list?.map((item) => (item.id === email.id ? { ...item, isRead: true } : item)),
      );
      return email;
    },
    enabled: emailId !== null,
    refetchOnWindowFocus: false,
  });
}

/** The extension's lookup of the open Gmail thread; null when AIMail has no email for it. */
export function useEmailByThread(threadId: string) {
  return useQuery({
    queryKey: queryKeys.emailByThread(threadId),
    queryFn: () => fetchEmailByThread(threadId),
  });
}

/**
 * An email already in hand, kept under the detail key so every draft action's response (written
 * there) updates it without another round trip. Never stale: refetching would regenerate.
 */
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

type RefineVariables = { emailId: string; instruction: string; draft: string };

export function useRefineEmail() {
  return useDraftMutation(({ emailId, instruction, draft }: RefineVariables) =>
    refineEmail(emailId, instruction, draft),
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
