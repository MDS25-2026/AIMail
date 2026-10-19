import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useIsDemo } from "../../demo/mode";
import { BACKEND_URL } from "../api/config";
import { queryKeys } from "./keys";
import { useSession } from "./session";

/**
 * Live inbox (specs/features/live-inbox.md): the backend's event stream, one per tab. An event is
 * a hint to refetch, never data: the list and the To-do come from their usual calls.
 */
export const EVENTS_URL = `${BACKEND_URL}/events`;
// Three drops in a row and the inbox polls until the stream is back.
export const FAILURES_BEFORE_POLLING = 3;
export const FALLBACK_POLL_MS = 60_000;
// A burst (a catch-up of 200 emails) refetches the list once, not 200 times.
export const COALESCE_MS = 500;

export type LiveState = "off" | "live" | "reconnecting";

const KINDS = ["new", "draft", "state", "resync"] as const;
type EventKind = (typeof KINDS)[number];
type MailboxEvent = { kind: EventKind; messageId: string | null };

export function useMailboxEvents(): LiveState {
  const queryClient = useQueryClient();
  const isDemo = useIsDemo();
  const isSignedIn = useSession().data !== undefined;
  const isActive = !isDemo && isSignedIn;
  const [state, setState] = useState<LiveState>("off");
  // Reset while rendering, not in the effect: a stream closed by sign-out never shows a stale "Live".
  const [wasActive, setWasActive] = useState(isActive);
  if (wasActive !== isActive) {
    setWasActive(isActive);
    setState("off");
  }
  useEffect(() => {
    if (!isActive || typeof EventSource === "undefined") return;
    return openStream(queryClient, setState);
  }, [queryClient, isActive]);
  return isActive ? state : "off";
}

function openStream(queryClient: QueryClient, setState: (state: LiveState) => void): () => void {
  const refetch = coalesced(() => invalidateInbox(queryClient), COALESCE_MS);
  let failures = 0;
  let poll: ReturnType<typeof setInterval> | undefined;
  const stopPolling = () => {
    if (poll !== undefined) clearInterval(poll);
    poll = undefined;
  };
  const source = new EventSource(EVENTS_URL, { withCredentials: true });
  source.onopen = () => {
    failures = 0;
    stopPolling();
    setState("live");
    refetch();
  };
  source.onerror = () => {
    failures += 1;
    setState("reconnecting");
    if (failures < FAILURES_BEFORE_POLLING || poll !== undefined) return;
    poll = setInterval(() => invalidateInbox(queryClient), FALLBACK_POLL_MS);
  };
  source.addEventListener("mailbox", (message) => {
    const event = parseEvent(dataOf(message));
    if (event === null) return;
    if (event.kind === "draft" && event.messageId !== null) {
      void queryClient.invalidateQueries({ queryKey: queryKeys.email(event.messageId) });
    }
    refetch();
  });
  return () => {
    source.close();
    stopPolling();
    refetch.cancel();
  };
}

function invalidateInbox(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: queryKeys.emails });
  void queryClient.invalidateQueries({ queryKey: queryKeys.todo });
}

function dataOf(message: Event): string | null {
  return message instanceof MessageEvent && typeof message.data === "string" ? message.data : null;
}

/** The backend's JSON, checked field by field: a stream is a boundary like any response. */
function parseEvent(data: string | null): MailboxEvent | null {
  if (data === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(data);
  } catch {
    return null;
  }
  if (typeof parsed !== "object" || parsed === null) return null;
  const kind = "kind" in parsed ? parsed.kind : undefined;
  const messageId = "messageId" in parsed ? parsed.messageId : null;
  const isKind = (value: unknown): value is EventKind =>
    typeof value === "string" && (KINDS as readonly string[]).includes(value);
  if (!isKind(kind) || (messageId !== null && typeof messageId !== "string")) return null;
  return { kind, messageId };
}

function coalesced(run: () => void, waitMs: number): (() => void) & { cancel: () => void } {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const trigger = () => {
    if (timer !== undefined) return;
    timer = setTimeout(() => {
      timer = undefined;
      run();
    }, waitMs);
  };
  trigger.cancel = () => {
    if (timer !== undefined) clearTimeout(timer);
    timer = undefined;
  };
  return trigger;
}
