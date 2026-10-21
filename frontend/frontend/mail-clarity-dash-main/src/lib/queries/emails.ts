import {
  type InfiniteData,
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import type { Email, EmailPage, Tone } from "../../types/email";
import {
  cancelSchedule,
  confirmSender,
  fetchEmail,
  fetchEmailByThread,
  fetchEmailPage,
  markUnread,
  refineEmail,
  regenerateEmail,
  scheduleEmail,
  sendEmail,
  snoozeEmail,
  translateDraft,
  translateEmail,
  unsnoozeEmail,
} from "../api/emails";
import { adaptTemplate } from "../api/templates";
import { useLiveState } from "../liveInbox";
import { refreshChangedEmails } from "./inboxRefresh";
import { queryKeys } from "./keys";

// While the worker writes the first draft (email.isDrafting), the email is fetched again on this
// beat; it gives up after DRAFT_POLL_LIMIT tries (two minutes), when Regenerate is the way on.
export const DRAFT_POLL_MS = 3_000;
export const DRAFT_POLL_LIMIT = 40;
// With the stream live a finished draft arrives as an event; a failed attempt writes no column the
// stream watches (generation_attempts), so this slower beat is what still ends "Drafting".
export const LIVE_DRAFT_POLL_MS = 30_000;

// Module level, so the query keeps its memoised result instead of re-flattening every render.
const everyLoadedEmail = (data: InfiniteData<EmailPage>) =>
  data.pages.flatMap((page) => page.emails);

/** The inbox, page by page; `data` is every loaded email, newest first, and fetchNextPage loads older. */
export function useEmails() {
  return useInfiniteQuery({
    queryKey: queryKeys.emails,
    queryFn: ({ pageParam }) => fetchEmailPage(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.nextCursor ?? undefined,
    select: everyLoadedEmail,
  });
}

/** One email's read state in the cached inbox list, so the unread marker changes now. */
function setListReadState(queryClient: QueryClient, emailId: string, isRead: boolean) {
  queryClient.setQueryData<InfiniteData<EmailPage>>(
    queryKeys.emails,
    (inbox) =>
      inbox && {
        ...inbox,
        pages: inbox.pages.map((page) => ({
          ...page,
          emails: page.emails.map((item) => (item.id === emailId ? { ...item, isRead } : item)),
        })),
      },
  );
}

/** The read state in both the list and the open email, so the marker and the toggle change now. */
function setReadState(queryClient: QueryClient, emailId: string, isRead: boolean) {
  setListReadState(queryClient, emailId, isRead);
  queryClient.setQueryData<Email>(queryKeys.email(emailId), (email) =>
    email ? { ...email, isRead } : email,
  );
}

/**
 * One email with its Lane C draft. Idle until something is selected, and keyed by id, so a
 * response for a previously selected email lands in that email's entry, never the one on
 * screen. No refetch on focus: the call marks the email read and is rate limited.
 * keepUnread: the reader marked it unread, so refreshing it must not mark it read again.
 */
export function useEmail(emailId: string | null, keepUnread = false) {
  const queryClient = useQueryClient();
  const draftPollMs = useLiveState() === "live" ? LIVE_DRAFT_POLL_MS : DRAFT_POLL_MS;
  return useQuery({
    queryKey: queryKeys.email(emailId ?? ""),
    // The signal cancels the request when the reader moves to another email before it answers.
    queryFn: async ({ signal }) => {
      const email = await fetchEmail(emailId ?? "", signal, keepUnread);
      setListReadState(queryClient, email.id, email.isRead);
      return email;
    },
    enabled: emailId !== null,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      query.state.data?.isDrafting && query.state.dataUpdateCount < DRAFT_POLL_LIMIT
        ? draftPollMs
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
/** The reader's reply, written in their language, in the email's language; nothing is stored. */
export const useTranslateDraft = () =>
  useMutation({
    mutationFn: ({ emailId, text }: { emailId: string; text: string }) =>
      translateDraft(emailId, text),
  });

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
 * rather than refetched (that endpoint re-runs generation). The list is refreshed instead, which
 * keeps Inbox and Sent consistent after a send: page 1 alone when the email is there.
 */
function useDraftMutation<TVariables>(mutationFn: (variables: TVariables) => Promise<Email>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.email(updated.id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.todo });
      void refreshChangedEmails(queryClient, new Set([updated.id]));
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
    mutationFn: ({
      emailId,
      draft,
      remindIfNoReply = false,
    }: {
      emailId: string;
      draft: string;
      remindIfNoReply?: boolean;
    }) => sendEmail(emailId, draft, remindIfNoReply),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.email(updated.id), updated);
      void queryClient.invalidateQueries({ queryKey: queryKeys.todo });
      void refreshChangedEmails(queryClient, new Set([updated.id]));
    },
    onError: (_error, { emailId }) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.email(emailId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
  });
}

/** Draft from template: the agent rewrites a saved template for the email, stored like a refine. */
export function useAdaptTemplate() {
  return useDraftMutation(adaptTemplate);
}

export const useScheduleEmail = () => useDraftMutation(scheduleEmail);
export const useCancelSchedule = () => useDraftMutation(cancelSchedule);
export const useSnoozeEmail = () => useDraftMutation(snoozeEmail);

export function useMarkUnread() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: markUnread,
    onSuccess: (_nothing, emailId) => setReadState(queryClient, emailId, false),
  });
}

/** Shown read at once; the server marks it read the way opening it does, so no route of its own. */
export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (emailId: string) => fetchEmail(emailId),
    onMutate: (emailId) => setReadState(queryClient, emailId, true),
    onSuccess: (email) => queryClient.setQueryData(queryKeys.email(email.id), email),
    onError: (_error, emailId) => setReadState(queryClient, emailId, false),
  });
}
export const useUnsnoozeEmail = () => useDraftMutation(unsnoozeEmail);

export function useConfirmSender() {
  return useDraftMutation(confirmSender);
}
