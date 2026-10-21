import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ComposeState,
  type ComposeDraft,
  type ComposeList,
  type ComposeSendFailure,
} from "../../types/compose";
import { ApiError, ApiErrorCode } from "../api/errors";
import {
  createComposeDraft,
  deleteComposeDraft,
  fetchComposeDraft,
  fetchComposeList,
  refineComposeDraft,
  saveComposeDraft,
  sendComposeDraft,
  settleComposeOutcome,
  writeComposeDraft,
} from "../api/compose";
import { withDraft, withoutDraft } from "../composeList";
import { queryKeys } from "./keys";

export function useComposeList() {
  return useQuery({ queryKey: queryKeys.composeList, queryFn: fetchComposeList });
}

// A claim Gmail never answered stays "sending" until the backend gives up on it, then turns into
// "outcome_unknown"; polling on this beat brings the "Was it sent?" question up without a reload.
export const SENDING_POLL_MS = 15_000;

/** One draft; no refetch on focus, so coming back to the tab never replaces what is on screen. */
export function useComposeDraftQuery(id: string | null) {
  return useQuery({
    queryKey: queryKeys.composeDraft(id ?? ""),
    queryFn: () => fetchComposeDraft(id ?? ""),
    enabled: id !== null,
    refetchOnWindowFocus: false,
    refetchInterval: (query) =>
      query.state.data?.state === ComposeState.Sending ? SENDING_POLL_MS : false,
  });
}

/** The last failed send of a draft, also one fired after its editor closed; null once retried. */
export function useComposeSendFailure(id: string) {
  return useQuery({
    queryKey: queryKeys.composeSendFailure(id),
    queryFn: (): ComposeSendFailure | null => null,
    enabled: false,
    staleTime: Infinity,
  });
}

const isConflict = (error: unknown) =>
  error instanceof ApiError && error.code === ApiErrorCode.Conflict;

/** The draft changed elsewhere while the model wrote: the answer was refused, so show what is stored. */
function useGenerationMutation<TVariables extends { id: string }>(
  mutationFn: (variables: TVariables) => Promise<ComposeDraft>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (draft) => storeDraft(queryClient, draft),
    onError: (error, { id }) => {
      if (isConflict(error)) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.composeDraft(id) });
      }
    },
  });
}

function storeDraft(queryClient: QueryClient, draft: ComposeDraft) {
  queryClient.setQueryData(queryKeys.composeDraft(draft.id), draft);
  queryClient.setQueryData<ComposeList>(
    queryKeys.composeList,
    (list) => list && withDraft(list, draft),
  );
}

/** Every change answers with the draft, so the cache is written directly and nothing refetches. */
function useComposeMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<ComposeDraft>,
) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn, onSuccess: (draft) => storeDraft(queryClient, draft) });
}

export const useCreateComposeDraft = () => useComposeMutation(createComposeDraft);

/** A refused save refetches: the email may have been sent from another tab meanwhile. */
export function useSaveComposeDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveComposeDraft,
    onSuccess: (draft) => storeDraft(queryClient, draft),
    onError: (_error, { id }) =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.composeDraft(id) }),
  });
}

export const useWriteComposeDraft = () => useGenerationMutation(writeComposeDraft);
export const useRefineComposeDraft = () => useGenerationMutation(refineComposeDraft);
export const useSettleComposeOutcome = () => useComposeMutation(settleComposeOutcome);

/** A failure also refetches: an unknown outcome leaves the draft locked as "may have been sent". */
export function useSendComposeDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: sendComposeDraft,
    onMutate: ({ id }) => queryClient.setQueryData(queryKeys.composeSendFailure(id), null),
    onSuccess: (draft) => {
      storeDraft(queryClient, draft);
      void queryClient.invalidateQueries({ queryKey: queryKeys.todo });
    },
    // Kept in the cache, not the editor: a send fired on leaving the draft has no editor to tell.
    onError: (error, { id }) => {
      const failure: ComposeSendFailure = { error };
      queryClient.setQueryData(queryKeys.composeSendFailure(id), failure);
      void queryClient.invalidateQueries({ queryKey: queryKeys.composeDraft(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.composeList });
    },
  });
}

export function useDeleteComposeDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteComposeDraft,
    // The draft's own entry stays: removing it while the editor is open would refetch a 404.
    onSuccess: (_nothing, id) =>
      queryClient.setQueryData<ComposeList>(
        queryKeys.composeList,
        (list) => list && withoutDraft(list, id),
      ),
  });
}
