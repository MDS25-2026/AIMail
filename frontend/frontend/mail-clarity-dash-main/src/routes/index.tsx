import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import InboxList from "../components/InboxList";
import EmailDetailPanel from "../components/EmailDetailPanel";
import SideNav from "../components/SideNav";
import { mockEmails } from "../mockData/emails";
import type { Tone } from "../types/email";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "iMail — AI inbox dashboard" },
      {
        name: "description",
        content:
          "iMail dashboard: prioritized inbox, AI summaries, action items, and approved-only draft replies.",
      },
      { property: "og:title", content: "iMail — AI inbox dashboard" },
      {
        property: "og:description",
        content:
          "Prioritized inbox with AI summaries, action items, and human-approved draft replies.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(mockEmails[0].id);
  const selectedEmail = mockEmails.find((email) => email.id === selectedEmailId) ?? null;

  // Draft + tone live here so the panels stay presentational.
  const [draft, setDraft] = useState(mockEmails[0].draftReply);
  const [tone, setTone] = useState<Tone>(mockEmails[0].tone);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRefining, setIsRefining] = useState(false);

  const handleSelectEmail = (emailId: string) => {
    const email = mockEmails.find((item) => item.id === emailId);
    if (!email) return;
    setSelectedEmailId(email.id);
    setDraft(email.draftReply);
    setTone(email.tone);
  };

  // --- Stubs: wire these to the real API later ---------------------------
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
  // -----------------------------------------------------------------------

  return (
    <div className="flex h-screen flex-col bg-slate-100">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight text-slate-900">iMail</span>
          <span className="text-xs text-slate-400">AI inbox assistant</span>
        </div>
        <Link to="/extension" className="text-sm font-medium text-blue-600 hover:text-blue-700">
          Extension panel preview
        </Link>
      </header>

      <main className="flex min-h-0 flex-1">
        <SideNav active="Inbox" />

        <aside className="w-80 shrink-0 border-r border-slate-200 bg-white">
          <InboxList
            emails={mockEmails}
            selectedEmailId={selectedEmailId}
            onSelectEmail={handleSelectEmail}
          />
        </aside>

        <section className="min-w-0 flex-1 bg-slate-50">
          <EmailDetailPanel
            email={selectedEmail}
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
        </section>
      </main>
    </div>
  );
}
