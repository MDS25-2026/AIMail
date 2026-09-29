import { useEffect } from "react";

const NEXT_KEYS = new Set(["ArrowDown", "j"]);
const PREVIOUS_KEYS = new Set(["ArrowUp", "k"]);

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/**
 * J/K and the arrow keys move through the inbox, the way mail clients do. Focus follows the
 * selection so a screen reader announces the newly selected email. Never while the reader is
 * typing: J in the draft is a letter, not a command.
 */
export function useInboxKeyboard(
  emailIds: string[],
  selectedId: string | null,
  onSelect: (emailId: string) => void,
): void {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isTyping(event.target) || event.altKey || event.ctrlKey || event.metaKey) return;
      const step = NEXT_KEYS.has(event.key) ? 1 : PREVIOUS_KEYS.has(event.key) ? -1 : 0;
      if (step === 0 || emailIds.length === 0) return;
      event.preventDefault();
      const current = selectedId === null ? -1 : emailIds.indexOf(selectedId);
      const next = emailIds[Math.min(Math.max(current + step, 0), emailIds.length - 1)];
      onSelect(next);
      document.querySelector<HTMLElement>(`[data-email-id="${CSS.escape(next)}"]`)?.focus();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [emailIds, selectedId, onSelect]);
}
