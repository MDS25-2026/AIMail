import { createContext, useContext } from "react";

import type { LiveState } from "./queries";

// The pages inside AppShell; the sign-in, status and extension preview pages never opened a stream.
const LIVE_INBOX_PATHS: ReadonlySet<string> = new Set([
  "/",
  "/admin",
  "/audit",
  "/compose",
  "/drafts",
  "/knowledge",
  "/scheduled",
  "/sent",
  "/settings",
  "/todo",
]);

export function hasLiveInbox(pathname: string): boolean {
  return LIVE_INBOX_PATHS.has(pathname);
}

/** The tab's one stream, held above the routes so moving between pages keeps it open. */
export const LiveInboxContext = createContext<LiveState>("off");

export function useLiveState(): LiveState {
  return useContext(LiveInboxContext);
}
