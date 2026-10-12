/** Pages anyone may open; finding no session there is expected, never a reason to leave for sign-in. */
const PUBLIC_PATHS: ReadonlySet<string> = new Set(["/signin", "/status"]);

export function isPublicPage(pathname: string): boolean {
  return PUBLIC_PATHS.has(pathname);
}
