import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import InboxList from "../components/InboxList";
import EmailDetailPanel from "../components/EmailDetailPanel";
import SideNav from "../components/SideNav";
import { fetchEmail, fetchEmails, refineEmail, regenerateEmail, sendEmail } from "../lib/api";
import type { Email, Tone } from "../types/email";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AIMail — AI inbox dashboard" },
      {
        name: "description",
        content:
          "AIMail dashboard: prioritized inbox, AI summaries, action items, and approved-only draft replies.",
      },
      { property: "og:title", content: "AIMail — AI inbox dashboard" },
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
  const [emails, setEmails] = useState<Email[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);

  // Draft + tone live here so the panels stay presentational.
  const [draft, setDraft] = useState("");
  const [tone, setTone] = useState<Tone>("professional");
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    fetchEmails().then(setEmails).catch(() => {});
  }, []);

  const requestSeqRef = useRef(0);
  const didAutoSelectRef = useRef(false);

  const handleSelectEmail = async (emailId: string) => {
    // Render list metadata immediately, then fill the Lane C draft when /emails/{id} returns
    // (that call runs the ~15s generation pipeline).
    const seq = ++requestSeqRef.current;
    const listEmail = emails.find((item) => item.id === emailId) ?? null;
    if (listEmail) {
      setSelectedEmail(listEmail);
      setDraft(listEmail.draftReply);
      setTone(listEmail.tone);
    }
    const detail = await fetchEmail(emailId).catch(() => null);
    // Only the newest selection's response wins. Guards both a later click and a duplicate
    // in-flight fetch for the same email (StrictMode) from clobbering the shown draft.
    if (detail && seq === requestSeqRef.current) {
      setSelectedEmail(detail);
      setDraft(detail.draftReply);
      setTone(detail.tone);
    }
  };

  useEffect(() => {
    // Auto-select the first email once; StrictMode double-invokes effects in dev.
    if (emails.length > 0 && !didAutoSelectRef.current) {
      didAutoSelectRef.current = true;
      void handleSelectEmail(emails[0].id);
    }
  }, [emails]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Stubs: wire these to the real API later ---------------------------
  // Apply a draft-mutating result only if it's still the latest request, so a double-click or
  // rapid tone-toggle can't let a slower earlier response clobber the newer draft.
  const applyIfLatest = (seq: number, updated: Email) => {
    if (seq !== requestSeqRef.current) return;
    setSelectedEmail(updated);
    setDraft(updated.draftReply);
  };

  const onRegenerate = async (emailId: string) => {
    const seq = ++requestSeqRef.current;
    setIsRegenerating(true);
    try {
      applyIfLatest(seq, await regenerateEmail(emailId, tone));
    } catch {
      // keep the current draft on failure
    } finally {
      if (seq === requestSeqRef.current) setIsRegenerating(false);
    }
  };

  const onRefine = async (emailId: string, instruction: string) => {
    const seq = ++requestSeqRef.current;
    setIsRefining(true);
    try {
      applyIfLatest(seq, await refineEmail(emailId, instruction, draft));
    } catch {
      // keep the current draft on failure
    } finally {
      if (seq === requestSeqRef.current) setIsRefining(false);
    }
  };

  const onToneChange = async (emailId: string, nextTone: Tone) => {
    setTone(nextTone);
    const seq = ++requestSeqRef.current;
    setIsRegenerating(true);
    try {
      applyIfLatest(seq, await regenerateEmail(emailId, nextTone));
    } catch {
      // keep the current draft on failure
    } finally {
      if (seq === requestSeqRef.current) setIsRegenerating(false);
    }
  };

  const onApproveSend = async (emailId: string) => {
    setIsSending(true);
    try {
      const updated = await sendEmail(emailId, draft);
      setSelectedEmail(updated);
      setEmails((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch {
      window.alert("Send failed — check the backend and email agent, then try again.");
    } finally {
      setIsSending(false);
    }
  };
  // -----------------------------------------------------------------------

  return (
    <div className="flex h-screen flex-col bg-slate-100">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight text-slate-900">AIMail</span>
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
            emails={emails}
            selectedEmailId={selectedEmail?.id ?? null}
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
            isSending={isSending}
          />
        </section>
      </main>
    </div>
  );
}
