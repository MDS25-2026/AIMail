import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  cancelHoldingReply,
  fetchHoldingReplies,
  fetchHoldingReplySettings,
  fetchPrivateMode,
  fetchScanReading,
  fetchSystemInfo,
  saveHoldingReplySettings,
  savePrivateMode,
  saveScanReading,
} from "../api/settings";
import { queryKeys } from "./keys";

// Replies wait in a queue the scheduler drains, so the list changes without the reader acting.
const HOLDING_REPLIES_REFRESH_MS = 60_000;

export function useSystemInfo() {
  return useQuery({ queryKey: queryKeys.systemInfo, queryFn: fetchSystemInfo });
}

export function useHoldingReplySettings() {
  return useQuery({
    queryKey: queryKeys.holdingReplySettings,
    queryFn: fetchHoldingReplySettings,
  });
}

/** The answer is what the server accepted, so it replaces the cached settings. */
export function useSaveHoldingReplySettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveHoldingReplySettings,
    onSuccess: (accepted) => queryClient.setQueryData(queryKeys.holdingReplySettings, accepted),
  });
}

export function useHoldingReplies() {
  return useQuery({
    queryKey: queryKeys.holdingReplies,
    queryFn: fetchHoldingReplies,
    refetchInterval: HOLDING_REPLIES_REFRESH_MS,
  });
}

export function useCancelHoldingReply() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cancelHoldingReply,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: queryKeys.holdingReplies }),
  });
}

export function usePrivateMode() {
  return useQuery({ queryKey: queryKeys.privateMode, queryFn: fetchPrivateMode });
}

export function useSavePrivateMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: savePrivateMode,
    onSuccess: (saved) => queryClient.setQueryData(queryKeys.privateMode, saved),
  });
}

export function useScanReading() {
  return useQuery({ queryKey: queryKeys.scanReading, queryFn: fetchScanReading });
}

export function useSaveScanReading() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveScanReading,
    onSuccess: (saved) => queryClient.setQueryData(queryKeys.scanReading, saved),
  });
}
