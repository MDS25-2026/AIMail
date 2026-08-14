import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import ExtensionPanel from "../components/ExtensionPanel";
import { mockEmails } from "../mockData/emails";
import type { Tone } from "../types/email";

export const Route = createFileRoute("/extension")({
  head: () => ({
    meta: [
      { title: "AIMail Chrome extension panel" },
      {
        name: "description",
        content:
          "Condensed AIMail side panel: AI summary, action items, and an approve-to-send draft reply.",
      },
      { property: "og:title", content: "AIMail Chrome extension panel" },
      {
        property: "og:description",
        content: "Condensed AIMail side panel with AI summary, action items, and draft reply.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ExtensionPage,
});

function ExtensionPage() {
  const email = mockEmails[0];
  const [draft, setDraft] = useState(email.draftReply);
  const [tone, setTone] = useState<Tone>(email.tone);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRefining, setIsRefining] = useState(false);

  const onRegenerate = (emailId: string) => {
    console.log("onRegenerate", { emailId, tone });
    setIsRegenerating(true);
    setTimeout(() => setIsRegenerating(false), 600);
  };

  const onRefine = (emailId: string, instruction: string) => {
    console.log("onRefine", { emailId, instruction, tone });
    setIsRefining(true);
    setTimeout(() => setIsRefining(false), 600);
  };

  const onToneChange = (emailId: string, nextTone: Tone) => {
    console.log("onToneChange", { emailId, tone: nextTone });
    setTone(nextTone);
  };

  const onApproveSend = (emailId: string) => {
    console.log("onApproveSend", { emailId, draft, tone });
  };

  return (
    <div className="min-h-screen bg-slate-100 p-8">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-sm font-semibold text-slate-700">Extension panel preview</h1>
        <Link to="/" className="text-sm font-medium text-blue-600 hover:text-blue-700">
          Back to dashboard
        </Link>
      </div>
      <div className="h-[720px]">
        <ExtensionPanel
          email={email}
          draft={draft}
          tone={tone}
          onDraftChange={setDraft}
          onToneChange={onToneChange}
          onRegenerate={onRegenerate}
          onRefine={onRefine}
          onApproveSend={onApproveSend}
          isRegenerating={isRegenerating}
          isRefining={isRefining}
        />
      </div>
    </div>
  );
}
