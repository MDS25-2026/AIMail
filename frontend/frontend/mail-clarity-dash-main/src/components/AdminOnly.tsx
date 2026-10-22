import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { isSignedOut } from "../lib/api/errors";
import { useSession } from "../lib/queries";
import NotFoundPage from "./NotFoundPage";
import { PageError } from "./PageState";

/**
 * An admin page (specs/features/admin-only-pages.md): to anyone else it does not exist. Children
 * mount only for an admin, so nobody else even asks the admin API; the server checks the role anyway.
 */
export default function AdminOnly({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const session = useSession();
  // Nothing while asking: neither the page nor a "not found" that would flash for an admin.
  if (session.isPending) return null;
  if (session.data?.isAdmin) return children;
  // An outage says nothing about who is asking: an admin must see it as one, not as a missing page.
  if (session.isError && !isSignedOut(session.error)) {
    return (
      <div className="min-h-screen bg-app py-6">
        <PageError
          label={t("page.thisPage")}
          error={session.error}
          onRetry={() => void session.refetch()}
        />
      </div>
    );
  }
  return <NotFoundPage />;
}
