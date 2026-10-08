import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { isSignedOut } from "../api/errors";
import { deleteAccount, disconnectGmail, fetchSession, signOut } from "../api/session";
import { queryKeys } from "./keys";

// While signed out, check again every couple of seconds, so signing in from a tab takes effect alone.
const SIGNED_OUT_POLL_MS = 2000;

/** Who is signed in. No retry: a 401 is an answer, and the cache handler sends them to sign in. */
export function useSession() {
  return useQuery({ queryKey: queryKeys.session, queryFn: fetchSession, retry: false });
}

/** The extension's session, which keeps asking while signed out so a sign-in in a tab lands alone. */
export function usePolledSession() {
  return useQuery({
    queryKey: queryKeys.session,
    queryFn: fetchSession,
    retry: false,
    refetchInterval: (query) => (isSignedOut(query.state.error) ? SIGNED_OUT_POLL_MS : false),
  });
}

/** Signing out clears every cached email from memory too, whether or not the server answered. */
export function useSignOut(onSignedOut: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signOut,
    onSettled: () => {
      queryClient.clear();
      onSignedOut();
    },
  });
}

export function useDisconnectGmail() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disconnectGmail,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.session });
      void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
    },
  });
}

/** Nothing of the account is left afterwards, so nothing of it may stay in the cache either. */
export function useDeleteAccount(onDeleted: () => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      queryClient.clear();
      onDeleted();
    },
  });
}
