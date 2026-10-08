import { createRouter } from "@tanstack/react-router";

import { createQueryClient } from "./lib/queries";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  // Any call that finds the session gone sends the reader to sign in, once, without retrying.
  const queryClient = createQueryClient({
    onSignedOut: () => void router.navigate({ to: "/signin" }),
  });

  const router = createRouter({
    routeTree,
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
