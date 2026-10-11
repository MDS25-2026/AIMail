import { useLocation } from "@tanstack/react-router";
import { useEffect, useRef } from "react";

export const MAIN_CONTENT_ID = "main-content";
// About a second at 60 fps; past that, the page's content area takes focus instead.
const HEADING_WAIT_FRAMES = 60;

/** After moving to another page, start keyboard and screen-reader users at its heading, as a full
 *  page load would. Only the path counts, so picking an email (?email=) never moves focus. */
export function useFocusOnNavigate(): void {
  const pathname = useLocation({ select: (location) => location.pathname });
  // The path focus was last set for: the first page, and a second run of the same effect (React's
  // development mode runs effects twice), leave focus where the browser put it.
  const focusedPath = useRef(pathname);
  useEffect(() => {
    if (focusedPath.current === pathname) return;
    focusedPath.current = pathname;
    // Pages load their code on demand: the old page stays on screen for a few frames, so wait for
    // a heading that is not the one already there.
    const headingSelector = `#${MAIN_CONTENT_ID} h1`;
    const previous = document.querySelector(headingSelector);
    let framesLeft = HEADING_WAIT_FRAMES;
    let frame = 0;
    const focusHeading = () => {
      const found = document.querySelector<HTMLElement>(headingSelector);
      const heading = found !== previous ? found : null;
      const isOutOfTime = framesLeft <= 0;
      // Out of time: the content area, if the page has one; sign-in and the extension preview do not.
      const target = heading ?? (isOutOfTime ? document.getElementById(MAIN_CONTENT_ID) : null);
      if (target) {
        target.tabIndex = -1;
        target.focus({ preventScroll: true });
        return;
      }
      if (isOutOfTime) return;
      framesLeft -= 1;
      frame = requestAnimationFrame(focusHeading);
    };
    frame = requestAnimationFrame(focusHeading);
    return () => cancelAnimationFrame(frame);
  }, [pathname]);
}
