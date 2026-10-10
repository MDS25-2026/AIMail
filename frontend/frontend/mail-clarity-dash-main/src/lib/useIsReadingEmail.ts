import { useLocation, useSearch } from "@tanstack/react-router";

/** An email open in the inbox: a full-screen step on a phone, where its send bar takes the bottom. */
export function useIsReadingEmail(): boolean {
  const pathname = useLocation({ select: (location) => location.pathname });
  const { email } = useSearch({ strict: false });
  return pathname === "/" && email !== undefined;
}
