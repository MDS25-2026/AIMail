/** Typed or pasted recipients as chips: "Name <addr@x.com>" and bare addresses alike. */

// Spaces are not among them: a display name has spaces.
const SEPARATORS = new Set([",", ";", "\n", "\r", "\t"]);

/** To and Cc together (backend/app/compose.py MAX_RECIPIENTS). */
export const MAX_RECIPIENTS = 20;
/** One address, as RFC 5321 allows (backend/app/compose.py MAX_ADDRESS_CHARS). */
export const MAX_ADDRESS_CHARS = 320;

// Loose on purpose: the backend checks every address on send; this only marks a likely typo.
const ADDRESS = /^[^\s@<>",;]+@[^\s@<>",;]+\.[^\s@<>",;.]+$/;
const ANGLE_ADDRESS = /<([^<>]*)>\s*$/;

export type SplitRecipients = { complete: string[]; rest: string };

type Scan = SplitRecipients & { isBalanced: boolean };

const tidy = (parts: string[]) => parts.map((part) => part.trim()).filter(Boolean);

function scan(text: string): Scan {
  const complete: string[] = [];
  let current = "";
  let isQuoted = false;
  let isInAngle = false;
  for (const char of text) {
    if (char === '"' && !isInAngle) isQuoted = !isQuoted;
    if (char === "<" && !isQuoted) isInAngle = true;
    if (char === ">" && !isQuoted) isInAngle = false;
    if (SEPARATORS.has(char) && !isQuoted && !isInAngle) {
      complete.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  return {
    complete: tidy(complete),
    rest: current.trimStart(),
    isBalanced: !isQuoted && !isInAngle,
  };
}

/**
 * While typing: the recipients finished by a separator, and the text after the last one. A comma
 * inside a "quoted display name" or <angle brackets> is part of the recipient, not a separator.
 */
export function splitRecipients(text: string): SplitRecipients {
  const { complete, rest } = scan(text);
  return { complete, rest };
}

/**
 * Every recipient in finished text (Enter, leaving the box, a paste). A quote or bracket left open
 * would swallow every separator after it, so then each separator counts.
 */
export function parseRecipients(text: string): string[] {
  const { complete, rest, isBalanced } = scan(text);
  if (!isBalanced) return tidy(text.split(/[,;\n\r\t]/));
  return tidy([...complete, rest]);
}

/** Whether the recipient looks like one address, bare or as "Name <address>". */
export function isLikelyAddress(recipient: string): boolean {
  const angle = ANGLE_ADDRESS.exec(recipient.trim());
  return ADDRESS.test((angle ? angle[1] : recipient).trim());
}

export type AcceptedRecipients = { accepted: string[]; tooLong: string[]; overLimit: string[] };

/** Which new recipients fit: none longer than one address may be, and no more than the limit. */
export function acceptRecipients(existing: number, incoming: string[]): AcceptedRecipients {
  const tooLong = incoming.filter((recipient) => recipient.length > MAX_ADDRESS_CHARS);
  const fitting = incoming.filter((recipient) => recipient.length <= MAX_ADDRESS_CHARS);
  const room = Math.max(0, MAX_RECIPIENTS - existing);
  return { accepted: fitting.slice(0, room), tooLong, overLimit: fitting.slice(room) };
}
