import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createTemplate,
  deleteTemplate,
  fetchTemplates,
  fillTemplate,
  translateTemplate,
  updateTemplate,
} from "../api/templates";
import { queryKeys } from "./keys";

export function useTemplates() {
  return useQuery({ queryKey: queryKeys.templates, queryFn: fetchTemplates });
}

/** Saving, editing or deleting changes the list, and filling changes which was used last. */
function useTemplateMutation<TVariables, TResult>(
  mutationFn: (variables: TVariables) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.templates }),
  });
}

export const useCreateTemplate = () => useTemplateMutation(createTemplate);
export const useUpdateTemplate = () => useTemplateMutation(updateTemplate);
export const useDeleteTemplate = () => useTemplateMutation(deleteTemplate);
export const useFillTemplate = () => useTemplateMutation(fillTemplate);

/** A translated copy for the form; nothing changes until it is saved. */
export function useTranslateTemplate() {
  return useMutation({ mutationFn: translateTemplate });
}
