import { createFileRoute } from "@tanstack/react-router";

import AppShell from "../components/AppShell";
import ComingSoon from "../components/ComingSoon";

export const Route = createFileRoute("/drafts")({
  head: () => ({ meta: [{ title: "AIMail Drafts" }] }),
  component: DraftsPage,
});

function DraftsPage() {
  return (
    <AppShell>
      <ComingSoon
        title="Drafts"
        description="Saved and in-progress replies will live here, so you can pick up a draft without reopening the thread it belongs to."
      />
    </AppShell>
  );
}
