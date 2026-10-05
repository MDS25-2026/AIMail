// The few Chrome extension APIs AIMail uses, typed by hand rather than adding @types/chrome.
// Messages arrive as `unknown`: they cross a process boundary and are narrowed by type guards.

declare namespace chrome {
  namespace runtime {
    type MessageSender = { tab?: tabs.Tab };
    type MessageListener = (
      message: unknown,
      sender: MessageSender,
      sendResponse: (response: unknown) => void,
    ) => boolean | undefined;
    function sendMessage(message: unknown): Promise<unknown>;
    const onMessage: {
      addListener(listener: MessageListener): void;
      removeListener(listener: MessageListener): void;
    };
  }

  namespace tabs {
    type Tab = { id?: number; url?: string; active: boolean; windowId: number };
    type ActiveInfo = { tabId: number; windowId: number };
    type ChangeInfo = { status?: string; url?: string };
    function query(filter: {
      active?: boolean;
      currentWindow?: boolean;
      url?: string;
    }): Promise<Tab[]>;
    function sendMessage(tabId: number, message: unknown): Promise<unknown>;
    function create(properties: { url: string }): Promise<Tab>;
    function remove(tabId: number): Promise<void>;
    const onActivated: {
      addListener(listener: (info: ActiveInfo) => void): void;
      removeListener(listener: (info: ActiveInfo) => void): void;
    };
    const onUpdated: {
      addListener(listener: (tabId: number, info: ChangeInfo, tab: Tab) => void): void;
      removeListener(listener: (tabId: number, info: ChangeInfo, tab: Tab) => void): void;
    };
  }

  namespace sidePanel {
    function setPanelBehavior(behavior: { openPanelOnActionClick: boolean }): Promise<void>;
    function setOptions(options: {
      tabId?: number;
      path?: string;
      enabled: boolean;
    }): Promise<void>;
  }
}
