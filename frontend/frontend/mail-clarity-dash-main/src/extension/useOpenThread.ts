import { useEffect, useState } from "react";

import { isGmailUrl } from "./gmailThread";
import { isThreadReport, MessageType, type WhichThread } from "./messages";

export enum TabState {
  Loading = "loading",
  NotGmail = "not-gmail",
  // A Gmail tab opened before the extension was installed has no content script until reloaded.
  NeedsReload = "needs-reload",
  Gmail = "gmail",
}

export type OpenThread = { tab: TabState; threadId: string | null };

const ASK: WhichThread = { type: MessageType.WhichThread };

/** The thread open in the active tab's Gmail, kept current as the reader moves around. */
export function useOpenThread(): OpenThread {
  const [state, setState] = useState<OpenThread>({ tab: TabState.Loading, threadId: null });

  useEffect(() => {
    let activeTabId: number | undefined;

    const ask = async () => {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      activeTabId = tab?.id;
      if (tab?.id === undefined || !isGmailUrl(tab.url)) {
        setState({ tab: TabState.NotGmail, threadId: null });
        return;
      }
      try {
        const reply = await chrome.tabs.sendMessage(tab.id, ASK);
        setState({ tab: TabState.Gmail, threadId: isThreadReport(reply) ? reply.threadId : null });
      } catch {
        setState({ tab: TabState.NeedsReload, threadId: null });
      }
    };

    const onMessage: chrome.runtime.MessageListener = (message, sender) => {
      if (isThreadReport(message) && sender.tab?.id === activeTabId) {
        setState({ tab: TabState.Gmail, threadId: message.threadId });
      }
      return undefined;
    };
    const onActivated = () => void ask();
    const onUpdated = (tabId: number, info: chrome.tabs.ChangeInfo) => {
      if (tabId === activeTabId && (info.url !== undefined || info.status === "complete"))
        void ask();
    };

    void ask();
    chrome.runtime.onMessage.addListener(onMessage);
    chrome.tabs.onActivated.addListener(onActivated);
    chrome.tabs.onUpdated.addListener(onUpdated);
    return () => {
      chrome.runtime.onMessage.removeListener(onMessage);
      chrome.tabs.onActivated.removeListener(onActivated);
      chrome.tabs.onUpdated.removeListener(onUpdated);
    };
  }, []);

  return state;
}
