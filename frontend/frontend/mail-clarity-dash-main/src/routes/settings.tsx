import { createFileRoute } from "@tanstack/react-router";

import AppShell from "../components/AppShell";
import ComingSoon from "../components/ComingSoon";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "AIMail Settings" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  return (
    <AppShell>
      <ComingSoon
        title="Settings"
        description="Tone defaults, the critic confidence threshold, and mailbox connection settings."
      />
    </AppShell>
  );
}
