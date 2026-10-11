import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  dismissEmail,
  draftFollowUp,
  fetchTodo,
  notWaiting,
  saveWaitingDays,
  sendFollowUp,
} from "../api/todo";
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

export const useDismissEmail = () => useTodoMutation(dismissEmail);
export const useNotWaiting = () => useTodoMutation(notWaiting);
export const useSaveWaitingDays = () => useTodoMutation(saveWaitingDays);
export const useSendFollowUp = () => useTodoMutation(sendFollowUp);

/** Drafting changes nothing stored, so the to-do list is left as it is. */
export const useDraftFollowUp = () => useMutation({ mutationFn: draftFollowUp });
