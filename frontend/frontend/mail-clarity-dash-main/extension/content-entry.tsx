import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

import panelCss from "./panel.css?inline";
import aimailLogoLight from "./aimail-logo-light.png";
import { observeGmailThread } from "./gmail-reader";
import ExtensionPanel from "../src/components/extension/ExtensionPanel";
import type { Email, Tone } from "../src/components/extension/types";
import { mockEmails } from "../src/mockData/emails";

/**
 * Gmail content script entry. Renders ExtensionPanel inside a Shadow DOM root
 * so Gmail's styles can't leak in (and ours can't leak out).
 *
 * The panel now reads the conversation that's actually open in Gmail via
 * gmail-reader.ts and falls back to mock data when no thread is open (or when
 * Gmail's DOM changes shape). AI actions remain stubbed.
 */
function ExtensionRoot() {
  const [open, setOpen] = useState(true);
  const [liveEmail, setLiveEmail] = useState<Email | null>(null);
  const email = liveEmail ?? mockEmails[0];
  const isLive = liveEmail !== null;

  const [draft, setDraft] = useState(email.draftReply);
  const [tone, setTone] = useState<Tone>(email.tone);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isRefining, setIsRefining] = useState(false);

  useEffect(() => observeGmailThread(setLiveEmail), []);

  // A new conversation means a new draft — don't carry the previous one over.
  useEffect(() => {
    setDraft(email.draftReply);
    setTone(email.tone);
  }, [email.id, email.draftReply, email.tone]);

  const onRegenerate = (emailId: string) => {
    console.log("onRegenerate", { emailId, tone });
    setIsRegenerating(true);
    setTimeout(() => {
      setDraft(email.draftReply);
      setIsRegenerating(false);
    }, 600);
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

  if (!open) {
    return (
      <div className="aimail-root">
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open AIMail panel"
          className="fixed bottom-4 right-4 z-[2147483647] flex items-center rounded-full border border-line bg-ink px-4 py-2.5 shadow-lg transition-colors hover:bg-[#1e293b]"
        >
          <img src={aimailLogoLight} alt="AIMail" className="h-4 w-auto" />
        </button>
      </div>
    );
  }

  return (
    <div className="aimail-root">
      <div className="aimail-panel fixed bottom-4 right-4 z-[2147483647] flex h-[720px] max-h-[85vh] w-[380px] flex-col">
        <div className="flex items-center justify-between gap-2 border-b border-line bg-surface px-3 py-1.5">
          <span
            className={`inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium ${
              isLive
                ? "bg-[#ecfdf5] text-ok ring-1 ring-inset ring-[#a7f3d0]"
                : "bg-app text-ink-muted ring-1 ring-inset ring-line"
            }`}
          >
            <span
              aria-hidden
              className={`h-1.5 w-1.5 rounded-full ${isLive ? "bg-ok" : "bg-ink-muted"}`}
            />
            {isLive ? "Reading open Gmail thread" : "Demo data — open a conversation"}
          </span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close AIMail panel"
            className="rounded p-1 text-ink-muted transition-colors hover:bg-app hover:text-ink"
          >
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 bg-app">
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
    </div>
  );
}

const HOST_ID = "aimail-extension-host";

if (!document.getElementById(HOST_ID)) {
  const host = document.createElement("div");
  host.id = HOST_ID;
  const shadow = host.attachShadow({ mode: "open" });

  const style = document.createElement("style");
  style.textContent = panelCss;
  shadow.appendChild(style);

  const mount = document.createElement("div");
  shadow.appendChild(mount);

  document.body.appendChild(host);
  createRoot(mount).render(<ExtensionRoot />);
}
