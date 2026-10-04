import type { KeyboardEvent } from "react";

const NEXT_KEYS = new Set(["ArrowDown", "j"]);
const PREVIOUS_KEYS = new Set(["ArrowUp", "k"]);

/**
 * J/K and the arrow keys move through the inbox, the way mail clients do. The handler goes on the
 * list itself, so the keys act only while focus is in it: single-letter shortcuts that fire
 * anywhere fail WCAG 2.1.4 (they trip speech-input users), and arrow keys elsewhere must scroll.
 * Focus follows the selection, so a screen reader announces the newly selected email.
 */
export function inboxKeyHandler(
  emailIds: string[],
  selectedId: string | null,
  onSelect: (emailId: string) => void,
) {
  return (event: KeyboardEvent<HTMLElement>) => {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const step = NEXT_KEYS.has(event.key) ? 1 : PREVIOUS_KEYS.has(event.key) ? -1 : 0;
    if (step === 0 || emailIds.length === 0) return;
    event.preventDefault();
    const current = selectedId === null ? -1 : emailIds.indexOf(selectedId);
    const next = emailIds[Math.min(Math.max(current + step, 0), emailIds.length - 1)];
    onSelect(next);
    document.querySelector<HTMLElement>(`[data-email-id="${CSS.escape(next)}"]`)?.focus();
  };
}
