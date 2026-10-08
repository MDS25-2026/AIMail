import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import ComingSoon from "../components/ComingSoon";
import { Page, pageMeta } from "../lib/pageMeta";

export const Route = createFileRoute("/drafts")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Drafts) }),
  component: DraftsPage,
});

function DraftsPage() {
  const { t } = useTranslation();
  return (
    <AppShell>
      <ComingSoon title={t("drafts.title")} description={t("drafts.description")} />
    </AppShell>
  );
}
