import { useSyncExternalStore } from "react";

/**
 * Demo mode (specs/features/demo-mailbox.md): a made-up mailbox anyone can try without signing in.
 * The flag lives in sessionStorage, so a reload stays in the demo and closing the tab ends it.
 */

const KEY = "aimail.demo";

// Storage can be blocked (private mode, strict settings) or absent (the server, where nothing
// starts the demo); the flag then lives here, until a reload.
let fallback = false;
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return window.sessionStorage.getItem(KEY) === "1";
  } catch {
    return fallback;
  }
}

function write(on: boolean) {
  fallback = on;
  try {
    if (on) window.sessionStorage.setItem(KEY, "1");
    else window.sessionStorage.removeItem(KEY);
  } catch {
    // The in-memory flag above stands in.
  }
  listeners.forEach((listener) => listener());
}

export const isDemo = read;
export const startDemo = () => write(true);
export const leaveDemo = () => write(false);

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** False on the server and the first client render, so both agree; the real value after mount. */
export function useIsDemo(): boolean {
  return useSyncExternalStore(subscribe, read, () => false);
}
