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

function withoutEmail(todo: Todo, emailId: string): Todo {
  const drop = (section: TodoSection): TodoSection => {
    const emails = section.emails.filter((email) => email.id !== emailId);
    return { emails, total: section.total - (section.emails.length - emails.length) };
  };
  return {
    ...todo,
    needsAction: drop(todo.needsAction),
    needsReview: drop(todo.needsReview),
    unsentDrafts: drop(todo.unsentDrafts),
  };
}

/** The row goes at once; on a slow host waiting for the server and a reload felt like lag. */
export function useDismissEmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: dismissEmail,
    onMutate: async (emailId: string) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.todo });
      const before = queryClient.getQueryData<Todo>(queryKeys.todo);
      if (before) queryClient.setQueryData(queryKeys.todo, withoutEmail(before, emailId));
      return { before };
    },
    onError: (_error, _emailId, context) => {
      if (context?.before) queryClient.setQueryData(queryKeys.todo, context.before);
    },
    onSettled: () => void queryClient.invalidateQueries({ queryKey: queryKeys.todo }),
  });
}
export const useNotWaiting = () => useTodoMutation(notWaiting);
export const useSaveWaitingDays = () => useTodoMutation(saveWaitingDays);
export const useSendFollowUp = () => useTodoMutation(sendFollowUp);

/** Drafting changes nothing stored, so the to-do list is left as it is. */
export const useDraftFollowUp = () => useMutation({ mutationFn: draftFollowUp });
