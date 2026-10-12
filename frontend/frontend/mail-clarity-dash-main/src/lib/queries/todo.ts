import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { snoozeEmail, unsnoozeEmail } from "../api/emails";
import {
  dismissEmail,
  draftFollowUp,
  fetchTodo,
  notWaiting,
  saveWaitingDays,
  sendFollowUp,
  undismissEmail,
  waitingAgain,
} from "../api/todo";
import type { Todo, TodoSection } from "../../types/todo";
import { queryKeys } from "./keys";

/** isEnabled: the sidebar asks only once the session says a mailbox is connected. */
export function useTodo(isEnabled = true) {
  return useQuery({
    queryKey: queryKeys.todo,
    queryFn: fetchTodo,
    enabled: isEnabled,
    retry: false,
  });
}

function useTodoMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.todo }),
  });
}

// Exported for tests; the nav badge reads count, so it drops with the row, not after the refetch.
export function withoutEmail(todo: Todo, emailId: string): Todo {
  const drop = (section: TodoSection): TodoSection => {
    const emails = section.emails.filter((email) => email.id !== emailId);
    return { emails, total: section.total - (section.emails.length - emails.length) };
  };
  const sections = {
    needsAction: drop(todo.needsAction),
    needsReview: drop(todo.needsReview),
    unsentDrafts: drop(todo.unsentDrafts),
  };
  const removed = (["needsAction", "needsReview", "unsentDrafts"] as const).reduce(
    (sum, key) => sum + todo[key].total - sections[key].total,
    0,
  );
  return { ...todo, ...sections, count: todo.count - removed };
}

export function withoutWaiting(todo: Todo, sentId: string): Todo {
  const waiting = todo.waiting.filter((reply) => reply.id !== sentId);
  return { ...todo, waiting, count: todo.count - (todo.waiting.length - waiting.length) };
}

/** Handled, so it counts towards "done today" at once; Remind me later is not done, only moved. */
export const handled = (todo: Todo, after: Todo): Todo =>
  after.count < todo.count ? { ...after, doneToday: todo.doneToday + 1 } : after;

/** The row goes at once; on a slow host waiting for the server and a reload felt like lag. */
function useInstantRemoval<TVariables>(
  mutationFn: (variables: TVariables) => Promise<unknown>,
  remove: (todo: Todo, variables: TVariables) => Todo,
  alsoChanged: readonly QueryKey[] = [],
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onMutate: async (variables: TVariables) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.todo });
      const before = queryClient.getQueryData<Todo>(queryKeys.todo);
      if (before) queryClient.setQueryData(queryKeys.todo, remove(before, variables));
      return { before };
    },
    onError: (_error, _variables, context) => {
      if (context?.before) queryClient.setQueryData(queryKeys.todo, context.before);
    },
    onSettled: () => {
      for (const queryKey of [queryKeys.todo, ...alsoChanged]) {
        void queryClient.invalidateQueries({ queryKey });
      }
    },
  });
}

export const useDismissEmail = () =>
  useInstantRemoval(dismissEmail, (todo, emailId: string) =>
    handled(todo, withoutEmail(todo, emailId)),
  );
export const useNotWaiting = () =>
  useInstantRemoval(notWaiting, (todo, sentId: string) =>
    handled(todo, withoutWaiting(todo, sentId)),
  );
export const useRemindLater = () =>
  // A snoozed email also leaves the inbox list, which would otherwise show it until its next refresh.
  useInstantRemoval(
    snoozeEmail,
    (todo, { emailId }: { emailId: string; until: Date }) => withoutEmail(todo, emailId),
    [queryKeys.emails],
  );

/** The undos: the row comes back with the refetch, since only the server knows where it sorts. */
function useUndo<TVariables>(mutationFn: (variables: TVariables) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.todo });
      void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
  });
}

export const useUndismissEmail = () => useUndo(undismissEmail);
export const useWaitingAgain = () => useUndo(waitingAgain);
export const useWakeEmail = () => useUndo(unsnoozeEmail);
export const useSaveWaitingDays = () => useTodoMutation(saveWaitingDays);
export const useSendFollowUp = () => useTodoMutation(sendFollowUp);

/** Drafting changes nothing stored, so the to-do list is left as it is. */
export const useDraftFollowUp = () => useMutation({ mutationFn: draftFollowUp });
