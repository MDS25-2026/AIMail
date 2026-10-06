import { useSyncExternalStore } from "react";

/**
 * "Hide details": show placeholders instead of the real values, for screen sharing and demos.
 * One flag for the whole page (header, body and draft stay in step), remembered per browser.
 */
const STORAGE_KEY = "aimail-hide-details";
const listeners = new Set<() => void>();

function read(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false; // no storage (server render, private mode): details are shown
  }
}

function write(isHidden: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, isHidden ? "1" : "0");
  } catch {
    // Not remembered for next time; the choice still applies now.
  }
  listeners.forEach((notify) => notify());
}

function subscribe(notify: () => void): () => void {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

export function useDetailsHidden(): [boolean, (isHidden: boolean) => void] {
  const isHidden = useSyncExternalStore(subscribe, read, () => false);
  return [isHidden, write];
}
