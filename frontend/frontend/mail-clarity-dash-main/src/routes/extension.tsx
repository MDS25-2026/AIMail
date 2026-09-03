import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

import ExtensionPanel from "../components/ExtensionPanel";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import {
  useEmail,
  useEmails,
  useRefineEmail,
  useRegenerateEmail,
  useSendEmail,
} from "../lib/queries";
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

/**
 * Preview of the condensed panel the Chrome extension renders inside Gmail.
 *
 * Runs on a real email rather than a fixture: the panel is the surface that will be wired to
 * this API, so previewing it against fabricated content proved nothing and put a fake sender
 * on screen during demos. Same page, same layout — the data and the buttons are now real.
 */
function ExtensionPage() {
  const emails = useEmails();
  // Prefer an email that already has a draft, so the panel previews a filled-in state rather
  // than an empty one; fall back to the newest email when nothing has been generated yet.
  const candidate = emails.data?.find((item) => item.draftReply) ?? emails.data?.[0] ?? null;
  const selected = useEmail(candidate?.id ?? null);
  const email = selected.data ?? candidate;

  const [draftOverride, setDraftOverride] = useState<string | null>(null);
  const [toneOverride, setToneOverride] = useState<Tone | null>(null);
  const draft = draftOverride ?? email?.draftReply ?? "";
  const tone = toneOverride ?? email?.tone ?? "professional";

  const regenerate = useRegenerateEmail();
  const refine = useRefineEmail();
  const send = useSendEmail();

  const clearOverrideOnSuccess = { onSuccess: () => setDraftOverride(null) };

  const onRegenerate = (emailId: string) => {
    regenerate.mutate({ emailId, tone }, clearOverrideOnSuccess);
  };

  const onRefine = (emailId: string, instruction: string) => {
    refine.mutate({ emailId, instruction, draft }, clearOverrideOnSuccess);
  };

  const onToneChange = (emailId: string, nextTone: Tone) => {
    setToneOverride(nextTone);
    regenerate.mutate({ emailId, tone: nextTone }, clearOverrideOnSuccess);
  };

  const onApproveSend = (emailId: string) => {
    send.mutate({ emailId, draft }, clearOverrideOnSuccess);
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
        {emails.isPending ? <PageLoading label="the panel preview" /> : null}
        {emails.isError ? <PageError label="the panel preview" error={emails.error} /> : null}
        {emails.data && !email ? (
          <PageEmpty
            title="No emails to preview"
            hint="Send a message to the connected mailbox and it will appear here."
          />
        ) : null}
        {email ? (
          <ExtensionPanel
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
          />
        ) : null}
      </div>
    </div>
  );
}
