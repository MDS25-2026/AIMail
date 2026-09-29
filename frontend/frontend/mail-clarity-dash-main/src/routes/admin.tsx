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
        {/* A failed refetch keeps the old data, so the error decides: signed out means the form. */}
        {!session.isPending && (session.isError || !session.data) ? <SignInForm /> : null}
        {session.isSuccess && session.data ? <AdminConsole admin={session.data} /> : null}
      </section>
    </AppShell>
  );
}
