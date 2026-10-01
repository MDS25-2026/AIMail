import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import ComingSoon from "../components/ComingSoon";

export const Route = createFileRoute("/drafts")({
  head: () => ({ meta: [{ title: "AIMail Drafts" }] }),
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
