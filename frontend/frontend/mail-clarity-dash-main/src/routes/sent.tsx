import { createFileRoute } from "@tanstack/react-router";

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
  return (
    <AppShell>
      <FilteredEmailList
        heading="Sent"
        description="Replies that were approved by a person and dispatched. Every row here required a click."
        label="sent replies"
        emptyTitle="Nothing sent yet"
        emptyHint="Approve a draft from the inbox and it will appear here."
        filter={(email) => Boolean(email.sentAt)}
        timestampOf={(email) => email.sentAt ?? email.timestamp}
      />
    </AppShell>
  );
}
