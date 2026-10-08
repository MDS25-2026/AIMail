/** Checks a draft for unprofessional tone patterns before sending. */

// Standard business & Malaysian enterprise acronyms that are capitalized but not shouting:
const ALLOWED_CAPS = new Set([
  "OK", "ASAP", "FYI", "FAQ", "ETA", "ID", "HR", "IT", "US", "UK", "API", "PR",
  // Malaysian corporate, statutory & tax acronyms:
  "PDPA", "LHDN", "KWSP", "EPF", "SOCSO", "PERKESO", "SST", "KPI", "CEO", "CTO", "CFO", "COO", "MOU", "NDA", "SOW"
]);

// Hostile/abusive words (strictly uncivil language, excluding ordinary business words like "terrible" or "unacceptable"):
const RUDE_PHRASES = [
  "stupid",
  "idiotic",
  "moron",
  "idiot",
  "dumb",
  "shut up",
  "incompetent",
  "disgrace",
  // Malay abusive words:
  "bodoh",
  "bangang",
  "babi",
  "sial",
  // Chinese abusive words:
  "白痴",
  "笨蛋",
  "滚",
  "混蛋"
];

// Matches Unicode emoji characters:
const EMOJI_RE = /\p{Emoji_Presentation}|\p{Extended_Pictographic}/gu;

export type ToneIssueCode = "CAPS" | "PUNCTUATION" | "RUDE" | "EMOJI";

export interface ToneCheckResult {
  hasIssues: boolean;
  issueCodes: ToneIssueCode[];
}

/**
 * Runs a lightweight, client-side tone check on `draft`.
 * Flags all-caps words (excluding allowlist), excessive punctuation (3+ !/?),
 * hostile/abusive phrasing, and excessive emojis (3+).
 */
export function checkTone(draft: string): ToneCheckResult {
  const issueCodes: ToneIssueCode[] = [];

  // 1. Consecutive or isolated all-caps words (3+ letters, not in the allow-list)
  const capsWords = draft.match(/\b[A-Z]{3,}\b/g) ?? [];
  const offendingCaps = capsWords.filter((w) => !ALLOWED_CAPS.has(w));
  if (offendingCaps.length >= 2 || (offendingCaps.length === 1 && draft.length < 50)) {
    issueCodes.push("CAPS");
  }

  // 2. Excessive repeated punctuation (3+ consecutive ! or ?)
  if (/[!?]{3,}/.test(draft)) {
    issueCodes.push("PUNCTUATION");
  }

  // 3. Rude / abusive phrases
  const rudePattern = RUDE_PHRASES.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const rudePhraseRe = new RegExp(`(?:\\b|(?<=[^a-zA-Z0-9]))(${rudePattern})(?:\\b|(?=[^a-zA-Z0-9]))`, "iu");
  if (rudePhraseRe.test(draft)) {
    issueCodes.push("RUDE");
  }

  // 4. Excessive emoji (3+)
  const emojiMatches = draft.match(EMOJI_RE) ?? [];
  if (emojiMatches.length >= 3) {
    issueCodes.push("EMOJI");
  }

  return {
    hasIssues: issueCodes.length > 0,
    issueCodes,
  };
}
