import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AdminOnly from "../components/AdminOnly";
import AppShell from "../components/AppShell";
import AuditTrailView from "../components/audit/AuditTrailView";
import { Page, pageMeta } from "../lib/pageMeta";

export const Route = createFileRoute("/audit")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Audit) }),
  component: AuditPage,
});

function AuditPage() {
  const { t } = useTranslation();
  return (
    <AdminOnly>
      <AppShell>
        <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-4 md:p-6">
          <div className="mx-auto max-w-6xl space-y-6">
            <header>
              <h1 className="text-2xl font-bold tracking-tight text-fg">{t("audit.title")}</h1>
              <p className="text-sm text-fg-muted">{t("audit.subtitle")}</p>
            </header>
            <AuditTrailView />
          </div>
        </section>
      </AppShell>
    </AdminOnly>
  );
}
