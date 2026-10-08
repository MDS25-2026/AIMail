import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AdminConsole from "../components/admin/AdminConsole";
import SignInForm from "../components/admin/SignInForm";
import AppShell from "../components/AppShell";
import { PageError, PageLoading } from "../components/PageState";
import { Page, pageMeta } from "../lib/pageMeta";
import { isAuthError, useAdminSession } from "../lib/queries";

export const Route = createFileRoute("/admin")({
  head: ({ match }) => ({
    meta: [
      ...pageMeta(match.context.preferences.language, Page.Admin),
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: AdminPage,
});

/** Signed in (by HttpOnly cookie, docs/adr/0004): the console. Otherwise: the sign-in form. */
function AdminPage() {
  const { t } = useTranslation();
  const session = useAdminSession();
  const isSignedOut = session.isError && isAuthError(session.error);

  return (
    <AppShell>
      <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
        {session.isPending ? <PageLoading label={t("admin.loading")} /> : null}
        {/* Signed out (a 401) means the form; any other failure is an error, not a sign-out: a
            network blip must not swap the console for a password prompt. A failed refetch keeps
            the old data, so the error decides. */}
        {isSignedOut ? <SignInForm /> : null}
        {session.isError && !isSignedOut ? (
          <PageError label={t("admin.loading")} error={session.error} />
        ) : null}
        {session.isSuccess && session.data ? <AdminConsole admin={session.data} /> : null}
      </section>
    </AppShell>
  );
}
