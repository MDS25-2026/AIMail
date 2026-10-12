import { createFileRoute } from "@tanstack/react-router";

import StatusPage from "../components/StatusPage";
import { Page, pageMeta } from "../lib/pageMeta";

// Outside AppShell, and its one call needs no sign-in, so a signed-out visitor stays here.
export const Route = createFileRoute("/status")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Status) }),
  component: StatusPage,
});
