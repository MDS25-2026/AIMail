// One address in a header like `Name <a@b.example>` or a bare `a@b.example`.
const ADDRESS = /[^\s<>,;"]+@[^\s<>,;"]+/g;

/**
 * The address a reply goes to when it is not the sender's, or null. Mirrors the backend
 * (app/gmail_send.py _single_address): a Reply-To naming several addresses is ignored there,
 * so the reply goes to the sender and there is nothing to warn about.
 */
export function replyGoesElsewhere(
  sender: string,
  replyTo: string | null | undefined,
): string | null {
  const replyAddresses = replyTo?.match(ADDRESS) ?? [];
  if (replyAddresses.length !== 1) return null;
  const [target] = replyAddresses;
  const senderAddress = sender.match(ADDRESS)?.[0] ?? "";
  return target.toLowerCase() === senderAddress.toLowerCase() ? null : target;
}
