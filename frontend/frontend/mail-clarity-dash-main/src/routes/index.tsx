import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import InboxList from "../components/InboxList";
import EmailDetailPanel from "../components/EmailDetailPanel";
import AppShell from "../components/AppShell";
import {
  useEmail,
  useEmails,
  useRefineEmail,
  useRegenerateEmail,
  useSendEmail,
} from "../lib/queries";
import type { Tone } from "../types/email";

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
  const emails = useEmails();
  const [selectedEmailId, setSelectedEmailId] = useState<string | null>(null);
  const selected = useEmail(selectedEmailId);

  // The detail call re-runs generation (~15s), so show the list row's copy until it lands.
  const listEmail = (emails.data ?? []).find((item) => item.id === selectedEmailId) ?? null;
  const email = selected.data ?? listEmail;

  // The draft is server state the user can type over. Rather than syncing state to the query in
  // an effect (which fights the user's keystrokes), an override shadows the server value and is
  // cleared whenever the server should win again: a new selection, or a completed mutation.
  const [draftOverride, setDraftOverride] = useState<string | null>(null);
  const [toneOverride, setToneOverride] = useState<Tone | null>(null);
  const draft = draftOverride ?? email?.draftReply ?? "";
  const tone = toneOverride ?? email?.tone ?? "professional";

  const regenerate = useRegenerateEmail();
  const refine = useRefineEmail();
  const send = useSendEmail();

  // Last issued wins. Query keys already stop a stale response landing on another email, but
  // two regenerates for the SAME email resolve into the same cache entry, so a slow first
  // response could still overwrite a newer one.
  const requestSeqRef = useRef(0);
  const runDraftMutation = (run: () => Promise<unknown>) => {
    const seq = ++requestSeqRef.current;
    void run()
      .then(() => {
        if (seq === requestSeqRef.current) setDraftOverride(null);
      })
      .catch(() => {
        // Keep whatever is on screen; the mutation's error state drives the UI.
      });
  };

  const handleSelectEmail = (emailId: string) => {
    setSelectedEmailId(emailId);
    setDraftOverride(null);
    setToneOverride(null);
  };

  const didAutoSelectRef = useRef(false);
  useEffect(() => {
    // Auto-select the first email once; StrictMode double-invokes effects in dev.
    const first = emails.data?.[0];
    if (first && !didAutoSelectRef.current) {
      didAutoSelectRef.current = true;
      handleSelectEmail(first.id);
    }
  }, [emails.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const onRegenerate = (emailId: string) => {
    runDraftMutation(() => regenerate.mutateAsync({ emailId, tone }));
  };

  const onRefine = (emailId: string, instruction: string) => {
    runDraftMutation(() => refine.mutateAsync({ emailId, instruction, draft }));
  };

  const onToneChange = (emailId: string, nextTone: Tone) => {
    setToneOverride(nextTone);
    runDraftMutation(() => regenerate.mutateAsync({ emailId, tone: nextTone }));
  };

  const onApproveSend = (emailId: string) => {
    send.mutate(
      { emailId, draft },
      {
        onSuccess: () => setDraftOverride(null),
        onError: () =>
          window.alert("Send failed — check the backend and email agent, then try again."),
      },
    );
  };

  return (
    <AppShell>
      <>
        <aside className="w-80 shrink-0 border-r border-slate-200 bg-white">
          <InboxList
            emails={emails.data ?? []}
            selectedEmailId={selectedEmailId}
            onSelectEmail={handleSelectEmail}
          />
        </aside>

        <section className="min-w-0 flex-1 bg-slate-50">
          <EmailDetailPanel
            email={email}
            draft={draft}
            tone={tone}
            onDraftChange={setDraftOverride}
            onToneChange={onToneChange}
            onRegenerate={onRegenerate}
            onRefine={onRefine}
            onApproveSend={onApproveSend}
            isRegenerating={regenerate.isPending}
            isRefining={refine.isPending}
            isSending={send.isPending}
          />
        </section>
      </>
    </AppShell>
  );
}
