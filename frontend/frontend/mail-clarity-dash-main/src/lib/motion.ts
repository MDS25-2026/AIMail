/** Whether the reader asked for less motion; false where the browser cannot say (tests, old browsers). */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches)
  );
}
