import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { addDocument, deleteDocument, fetchDocuments, uploadDocument } from "../api/documents";
import { queryKeys } from "./keys";

export function useDocuments() {
  return useQuery({ queryKey: queryKeys.documents, queryFn: fetchDocuments });
}

/** Any change to the library changes the corpus stats too, so both entries are invalidated. */
function useLibraryChange<TInput, TResult>(mutationFn: (input: TInput) => Promise<TResult>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.documents });
      void queryClient.invalidateQueries({ queryKey: queryKeys.systemInfo });
    },
  });
}

export function useDeleteDocument() {
  return useLibraryChange(deleteDocument);
}

export function useUploadDocument() {
  return useLibraryChange(uploadDocument);
}

export function useAddDocument() {
  return useLibraryChange(({ title, text }: { title: string; text: string }) =>
    addDocument(title, text),
  );
}
