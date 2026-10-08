import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { WritingStyle } from "../../types/profile";
import {
  addStyleExample,
  deleteStyleExample,
  deleteWritingStyle,
  fetchWritingStyle,
  hideStyleHabit,
  saveStyleDescription,
  setStyleLearning,
} from "../api/profile";
import { queryKeys } from "./keys";

export function useWritingStyle() {
  return useQuery({ queryKey: queryKeys.writingStyle, queryFn: fetchWritingStyle });
}

/** A change that answers with the whole stored style replaces the cache; one that does not refetches. */
function useStyleChange<TInput>(change: (input: TInput) => Promise<WritingStyle | void>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (style) => {
      if (style) {
        queryClient.setQueryData(queryKeys.writingStyle, style);
        return;
      }
      void queryClient.invalidateQueries({ queryKey: queryKeys.writingStyle });
    },
  });
}

export const useSaveStyleDescription = () => useStyleChange(saveStyleDescription);
export const useSetStyleLearning = () => useStyleChange(setStyleLearning);
export const useAddStyleExample = () => useStyleChange(addStyleExample);
export const useDeleteStyleExample = () => useStyleChange(deleteStyleExample);
export const useHideStyleHabit = () => useStyleChange(hideStyleHabit);
export const useDeleteWritingStyle = () => useStyleChange(deleteWritingStyle);
