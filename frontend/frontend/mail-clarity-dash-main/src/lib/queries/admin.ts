import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  fetchAdminSession,
  fetchCompanyQuietHours,
  fetchFlagged,
  fetchOverview,
  isAuthError,
  retryUnlessAuth,
  saveCompanyQuietHours,
  signIn,
  signOut,
} from "../adminApi";
import { queryKeys } from "./keys";

export { isAuthError } from "../adminApi";

const keys = queryKeys.admin;

/** Who is signed in to the console (docs/adr/0004). A 401 is an answer ("nobody"), not retried. */
export function useAdminSession() {
  return useQuery({ queryKey: keys.session, queryFn: fetchAdminSession, retry: false });
}

/**
 * Whether the console signed in with its own form (docs/adr/0004). The cookies are HttpOnly, so only
 * this tab knows: after a reload the button hides and the console cookie lasts until it expires.
 */
export function useHasOwnAdminSession(): boolean {
  const query = useQuery({
    queryKey: keys.hasOwnSession,
    queryFn: () => false,
    staleTime: Infinity,
  });
  return query.data === true;
}

export function useAdminOverview(days: number, isEnabled: boolean) {
  return useQuery({
    queryKey: keys.overview(days),
    queryFn: () => fetchOverview(days),
    enabled: isEnabled,
    retry: retryUnlessAuth,
  });
}

export function useAdminFlagged(isEnabled: boolean) {
  return useQuery({
    queryKey: keys.flagged,
    queryFn: fetchFlagged,
    enabled: isEnabled,
    retry: retryUnlessAuth,
  });
}

export function useAdminSignIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      signIn(email, password),
    onSuccess: (identity) => {
      queryClient.setQueryData(keys.session, identity);
      queryClient.setQueryData(keys.hasOwnSession, true);
      // Panels that failed while signed out must fetch again for the new session.
      void queryClient.invalidateQueries({
        queryKey: keys.all,
        predicate: (query) =>
          query.queryKey[1] !== keys.session[1] && query.queryKey[1] !== keys.hasOwnSession[1],
      });
    },
  });
}

/**
 * When any console panel finds the session gone (after its one refresh), ask again who is signed
 * in: the session query then fails too, and the page falls back to the sign-in form.
 */
export function useSignedOutRecovery(errors: unknown[]): void {
  const queryClient = useQueryClient();
  const isSignedOut = errors.some(isAuthError);
  useEffect(() => {
    if (isSignedOut) void queryClient.invalidateQueries({ queryKey: keys.session });
  }, [isSignedOut, queryClient]);
}

/**
 * Signing out resets every admin query. resetQueries, not removeQueries: a removed query tells
 * its mounted observers nothing, so the console stayed on screen with the old identity.
 */
export function useAdminSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signOut,
    onSettled: () => queryClient.resetQueries({ queryKey: keys.all }),
  });
}

export function useCompanyQuietHours(isEnabled: boolean) {
  return useQuery({
    queryKey: keys.quietHours,
    queryFn: fetchCompanyQuietHours,
    enabled: isEnabled,
    retry: retryUnlessAuth,
  });
}

export function useSaveCompanyQuietHours() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveCompanyQuietHours,
    onSuccess: (saved) => queryClient.setQueryData(keys.quietHours, saved),
  });
}
