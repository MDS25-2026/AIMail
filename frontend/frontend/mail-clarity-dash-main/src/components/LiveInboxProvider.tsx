import { useLocation } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { hasLiveInbox, LiveInboxContext } from "../lib/liveInbox";
import { useMailboxEvents } from "../lib/queries";

/** Mounted once at the root: a page change no longer closes the stream and refetches on reopen. */
export default function LiveInboxProvider({ children }: { children: ReactNode }) {
  const isEnabled = useLocation({ select: (location) => hasLiveInbox(location.pathname) });
  const live = useMailboxEvents({ isEnabled });
  return <LiveInboxContext.Provider value={live}>{children}</LiveInboxContext.Provider>;
}
