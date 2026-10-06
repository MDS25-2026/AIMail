import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";

import { SignedOutError } from "./lib/api";
import { routeTree } from "./routeTree.gen";

const MAX_RETRIES = 3;

export const getRouter = () => {
  // Any call that finds the session gone sends the reader to sign in, once, without retrying.
  const toSignIn = (error: unknown) => {
    if (error instanceof SignedOutError) void router.navigate({ to: "/signin" });
  };
  const queryClient = new QueryClient({
    queryCache: new QueryCache({ onError: toSignIn }),
    mutationCache: new MutationCache({ onError: toSignIn }),
    defaultOptions: {
      queries: {
        retry: (failures, error) => !(error instanceof SignedOutError) && failures < MAX_RETRIES,
      },
    },
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
