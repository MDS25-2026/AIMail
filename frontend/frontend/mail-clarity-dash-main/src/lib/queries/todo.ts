import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { dismissEmail, fetchTodo, notWaiting, saveWaitingDays } from "../api/todo";
import { queryKeys } from "./keys";

export function useTodo() {
  return useQuery({ queryKey: queryKeys.todo, queryFn: fetchTodo });
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
