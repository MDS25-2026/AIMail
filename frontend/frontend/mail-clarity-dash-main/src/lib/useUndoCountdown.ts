import { useCallback, useEffect, useRef, useState } from "react";

/** Duration of the undo window in seconds, for replies and new emails alike. */
export const UNDO_COUNTDOWN_SECONDS = 5;
const TICK_MS = 1_000;

export type UndoCountdown = {
  /** Seconds left before the approved send goes out; null outside the undo window. */
  secondsLeft: number | null;
  /** Starts the window; `send` runs when it ends, unless undone. */
  start: (send: () => void) => void;
  /** Cancels the send; nothing goes out. */
  undo: () => void;
  /** Ends the window by sending now, for when the email leaves the screen. */
  sendNow: () => void;
};

/** The undo window before a send. Unmounting mid-window sends at once: the user approved it. */
export function useUndoCountdown(): UndoCountdown {
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingSendRef = useRef<(() => void) | null>(null);

  const undo = useCallback(() => {
    if (timerRef.current !== null) clearInterval(timerRef.current);
    timerRef.current = null;
    pendingSendRef.current = null;
    setSecondsLeft(null);
  }, []);

  const sendNow = useCallback(() => {
    const pendingSend = pendingSendRef.current;
    undo();
    pendingSend?.();
  }, [undo]);

  useEffect(() => sendNow, [sendNow]);

  const start = useCallback(
    (send: () => void) => {
      sendNow();
      pendingSendRef.current = send;
      let remaining = UNDO_COUNTDOWN_SECONDS;
      setSecondsLeft(remaining);
      timerRef.current = setInterval(() => {
        remaining -= 1;
        if (remaining > 0) {
          setSecondsLeft(remaining);
          return;
        }
        sendNow();
      }, TICK_MS);
    },
    [sendNow],
  );

  return { secondsLeft, start, undo, sendNow };
}
