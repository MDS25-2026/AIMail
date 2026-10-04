import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import FilteredEmailList from "../components/FilteredEmailList";

export const Route = createFileRoute("/sent")({
  head: () => ({
    meta: [
      { title: "AIMail sent" },
      { name: "description", content: "Replies a human approved and AImail sent." },
    ],
  }),
  component: SentPage,
});

function SentPage() {
  const { t } = useTranslation();
  return (
    <AppShell>
      <FilteredEmailList
        heading={t("sent.heading")}
        description={t("sent.description")}
        label={t("sent.label")}
        emptyTitle={t("sent.emptyTitle")}
        emptyHint={t("sent.emptyHint")}
        filter={(email) => Boolean(email.sentAt)}
        timestampOf={(email) => email.sentAt ?? email.timestamp}
      />
    </AppShell>
  );
}
