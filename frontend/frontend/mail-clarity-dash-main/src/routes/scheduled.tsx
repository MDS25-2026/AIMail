import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import FilteredEmailList from "../components/FilteredEmailList";
import { ListOrder } from "../lib/listOrder";
import { Page, pageMeta } from "../lib/pageMeta";

export const Route = createFileRoute("/scheduled")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Scheduled) }),
  component: ScheduledPage,
});

/** Replies held for later (specs/features/quiet-hours-send-later.md); open one to cancel it. */
function ScheduledPage() {
  const { t } = useTranslation();
  return (
    <AppShell>
      <FilteredEmailList
        heading={t("scheduled.heading")}
        description={t("scheduled.description")}
        label={t("scheduled.label")}
        emptyTitle={t("scheduled.emptyTitle")}
        emptyHint={t("scheduled.emptyHint")}
        filter={(email) => Boolean(email.scheduledFor)}
        timestampOf={(email) => email.scheduledFor ?? email.timestamp}
        order={ListOrder.SoonestFirst}
      />
    </AppShell>
  );
}
