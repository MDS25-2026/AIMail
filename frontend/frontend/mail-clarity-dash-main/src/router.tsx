import { createRouter } from "@tanstack/react-router";

import { isPublicPage } from "./lib/publicPages";
import { createQueryClient } from "./lib/queries";
import { routeTree } from "./routeTree.gen";

export const getRouter = () => {
  // Any call that finds the session gone sends the reader to sign in, once, without retrying;
  // not from a public page, where the chat widget's session check found no one, as expected.
  const queryClient = createQueryClient({
    onSignedOut: () => {
      if (isPublicPage(router.state.location.pathname)) return;
      void router.navigate({ to: "/signin" });
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
