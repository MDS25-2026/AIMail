import { createFileRoute } from "@tanstack/react-router";

import AdminConsoleGate from "../components/admin/AdminConsoleGate";
import AdminOnly from "../components/AdminOnly";
import AppShell from "../components/AppShell";
import NotInDemo from "../components/NotInDemo";
import { Page, pageMeta } from "../lib/pageMeta";

export const Route = createFileRoute("/admin")({
  head: ({ match }) => ({
    meta: [
      ...pageMeta(match.context.preferences.language, Page.Admin),
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: AdminPage,
});

/** The demo counts as an admin for the Audit Trail only: the console shows real company data. */
function AdminPage() {
  return (
    <NotInDemo>
      <AdminOnly>
        <AppShell>
          <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-4 md:p-6">
            <AdminConsoleGate />
          </section>
        </AppShell>
      </AdminOnly>
    </NotInDemo>
  );
}
