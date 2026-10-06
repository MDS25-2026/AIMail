/** Opens the side panel from the toolbar icon, and offers it only on Gmail tabs. */
import { isGmailUrl } from "./gmailThread";

const PANEL_PATH = "sidepanel.html";
const GMAIL_TABS = "https://mail.google.com/*";

function enableOn(tabId: number | undefined, isEnabled: boolean): void {
  if (tabId === undefined) return;
  void chrome.sidePanel.setOptions({ tabId, path: PANEL_PATH, enabled: isEnabled });
}

void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
// Off by default; each Gmail tab turns it on below (a tab's own setting wins over this one).
void chrome.sidePanel.setOptions({ enabled: false });

// A tab's URL is only visible here for hosts the extension may access, so anything else reads
// as "not Gmail".
chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.status !== "complete" && info.url === undefined) return;
  enableOn(tabId, isGmailUrl(tab.url));
});

// Gmail tabs already open when the extension is installed (or the worker restarts) never fire the
// update above, and the panel would stay switched off there.
void chrome.tabs
  .query({ url: GMAIL_TABS })
  .then((tabs) => tabs.forEach((tab) => enableOn(tab.id, true)));
