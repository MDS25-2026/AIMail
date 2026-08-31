import { createFileRoute } from "@tanstack/react-router";

import AppShell from "../components/AppShell";
import ComingSoon from "../components/ComingSoon";

export const Route = createFileRoute("/knowledge")({
  head: () => ({ meta: [{ title: "AIMail Knowledge base" }] }),
  component: KnowledgebasePage,
});

function KnowledgebasePage() {
  return (
    <AppShell>
      <ComingSoon
        title="Knowledge base"
        description="The documents AImail retrieves from when grounding a reply. Upload and management move here from the demo endpoints."
      />
    </AppShell>
  );
}
