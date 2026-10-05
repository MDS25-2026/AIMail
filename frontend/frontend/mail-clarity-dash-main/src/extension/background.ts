/** Opens the side panel from the toolbar icon, and offers it only on Gmail tabs. */
import { isGmailUrl } from "./gmailThread";

const PANEL_PATH = "sidepanel.html";

void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
// Off by default; each Gmail tab turns it on below (a tab's own setting wins over this one).
void chrome.sidePanel.setOptions({ enabled: false });

// A tab's URL is only visible here for hosts the extension may access, so anything else reads
// as "not Gmail".
chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.status !== "complete" && info.url === undefined) return;
  void chrome.sidePanel.setOptions({ tabId, path: PANEL_PATH, enabled: isGmailUrl(tab.url) });
});
