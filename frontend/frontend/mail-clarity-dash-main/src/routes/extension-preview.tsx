import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import ExtensionPanel from "../components/extension/ExtensionPanel";
import { mockEmails } from "../mockData/emails";
import type { Tone } from "../types/email";

export const Route = createFileRoute("/extension-preview")({
  head: () => ({
    meta: [
      { title: "AIMail panel preview — standalone" },
      {
        name: "description",
        content:
          "Standalone 380px preview of the AIMail Chrome extension panel, rendered without any dashboard chrome.",
      },
      { property: "og:title", content: "AIMail panel preview — standalone" },
      {
        property: "og:description",
        content: "The AIMail side panel exactly as it will appear mounted inside Gmail.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ExtensionPreviewPage,
});

function ExtensionPreviewPage() {
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

  const downloadExtension = () => {
    fetch("/aimail-extension.zip")
      .then((res) => {
        if (!res.ok) throw new Error(`Download failed: ${res.status}`);
        return res.blob();
      })
      .then((blob) => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "aimail-extension.zip";
        a.click();
        URL.revokeObjectURL(a.href);
      })
      .catch((err) => alert(err.message));
  };

  return (
    <div className="flex min-h-screen justify-center gap-8 bg-slate-200 py-8">
      <div className="h-[720px] w-[380px]">
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

      <aside className="h-fit w-72 space-y-4 rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="text-sm font-semibold text-slate-900">Get the Chrome extension</h2>
        <p className="text-xs leading-relaxed text-slate-500">
          Run this panel inside Gmail as a Manifest V3 extension (mock data, AI actions stubbed).
        </p>
        <button
          type="button"
          onClick={downloadExtension}
          className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          Download extension (.zip)
        </button>
        <ol className="list-decimal space-y-1.5 pl-4 text-xs leading-relaxed text-slate-600">
          <li>Unzip the downloaded file.</li>
          <li>
            Open <span className="font-mono text-slate-800">chrome://extensions</span> in Chrome (or
            any Chromium browser).
          </li>
          <li>
            Enable <span className="font-medium text-slate-800">Developer mode</span> (top-right
            toggle).
          </li>
          <li>
            Click <span className="font-medium text-slate-800">Load unpacked</span> and select the
            unzipped folder.
          </li>
          <li>Open Gmail — the AIMail panel appears in the bottom-right corner.</li>
        </ol>
      </aside>
    </div>
  );
}
