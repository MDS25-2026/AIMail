import { useTranslation } from "react-i18next";

import { isAuthError, useAdminSession } from "../../lib/queries";
import { PageError, PageLoading } from "../PageState";
import AdminConsole from "./AdminConsole";
import SignInForm from "./SignInForm";

/**
 * Only an admin gets here, and the console API accepts their dashboard cookie, so the console
 * opens directly. The form is the fallback for a 401: a password-only admin account (docs/adr/0004).
 */
export default function AdminConsoleGate() {
  const { t } = useTranslation();
  const session = useAdminSession();
  const isSignedOut = session.isError && isAuthError(session.error);

  return (
    <>
      {session.isPending ? <PageLoading label={t("admin.loading")} /> : null}
      {/* Signed out (a 401) means the form; any other failure is an error, not a sign-out: a
          network blip must not swap the console for a password prompt. A failed refetch keeps
          the old data, so the error decides. */}
      {isSignedOut ? <SignInForm /> : null}
      {session.isError && !isSignedOut ? (
        <PageError label={t("admin.loading")} error={session.error} />
      ) : null}
      {session.isSuccess && session.data ? <AdminConsole admin={session.data} /> : null}
    </>
  );
}
