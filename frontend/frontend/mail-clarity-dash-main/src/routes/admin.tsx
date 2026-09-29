import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AdminConsole from "../components/admin/AdminConsole";
import SignInForm from "../components/admin/SignInForm";
import AppShell from "../components/AppShell";
import { PageLoading } from "../components/PageState";
import { useAdminSession } from "../lib/queries";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [{ title: "AIMail admin" }, { name: "robots", content: "noindex, nofollow" }],
  }),
  component: AdminPage,
});

/** Signed in (by HttpOnly cookie, docs/adr/0004): the console. Otherwise: the sign-in form. */
function AdminPage() {
  const { t } = useTranslation();
  const session = useAdminSession();

  return (
    <AppShell>
      <section className="min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
        {session.isPending ? <PageLoading label={t("admin.loading")} /> : null}
        {session.data ? <AdminConsole admin={session.data} /> : null}
        {session.isError ? <SignInForm /> : null}
      </section>
    </AppShell>
  );
}
