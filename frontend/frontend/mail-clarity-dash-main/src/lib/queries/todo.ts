import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  dismissEmail,
  draftFollowUp,
  fetchTodo,
  notWaiting,
  saveWaitingDays,
  sendFollowUp,
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

/** The row goes at once; on a slow host waiting for the server and a reload felt like lag. */
function useInstantRemoval(
  mutationFn: (id: string) => Promise<void>,
  remove: (todo: Todo, id: string) => Todo,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.todo });
      const before = queryClient.getQueryData<Todo>(queryKeys.todo);
      if (before) queryClient.setQueryData(queryKeys.todo, remove(before, id));
      return { before };
    },
    onError: (_error, _id, context) => {
      if (context?.before) queryClient.setQueryData(queryKeys.todo, context.before);
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: queryKeys.todo }),
  });
}

export const useDismissEmail = () => useInstantRemoval(dismissEmail, withoutEmail);
export const useNotWaiting = () => useInstantRemoval(notWaiting, withoutWaiting);
export const useSaveWaitingDays = () => useTodoMutation(saveWaitingDays);
export const useSendFollowUp = () => useTodoMutation(sendFollowUp);

/** Drafting changes nothing stored, so the to-do list is left as it is. */
export const useDraftFollowUp = () => useMutation({ mutationFn: draftFollowUp });
