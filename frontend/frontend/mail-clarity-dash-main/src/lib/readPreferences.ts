import { createIsomorphicFn } from "@tanstack/react-start";
import { getCookie } from "@tanstack/react-start/server";

import { parsePreferences, type Preferences } from "./preferences";

// Kept apart from preferences.ts: the server half pulls in TanStack Start, which the Chrome
// extension's plain Vite build cannot include.
function browserCookie(name: string): string | undefined {
  const match = document.cookie.split("; ").find((pair) => pair.startsWith(`${name}=`));
  if (!match) return undefined;
  try {
    return decodeURIComponent(match.slice(name.length + 1));
  } catch {
    // A malformed value (cookies on localhost are shared across ports) is just "not set".
    return undefined;
  }
}

export const readPreferences = createIsomorphicFn()
  .server((): Preferences => parsePreferences(getCookie))
  .client((): Preferences => parsePreferences(browserCookie));
