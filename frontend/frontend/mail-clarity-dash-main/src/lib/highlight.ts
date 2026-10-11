/**
 * Which sentences of a source passage the draft draws on, by shared wording.
 *
 * Lexical overlap, not meaning: it points the reviewer at the likely sentence to check, and a
 * paraphrase it misses costs a glance, not a wrong verdict. Short and common words are ignored so
 * "the" and "please" never make a match.
 */

const MIN_WORD_LENGTH = 4;
const MIN_SHARED_WORDS = 3;
// Chinese ends a sentence with 。！？ and no space after it.
const SENTENCE_BREAK = /(?<=[.!?])\s+|(?<=[。！？])/;
const HAN = /\p{Script=Han}/u;
const WORD = /[\p{L}\p{N}]+/gu;
const COMMON = new Set([
  "that",
  "this",
  "with",
  "from",
  "have",
  "will",
  "your",
  "their",
  "there",
  "which",
  "would",
  "should",
  "could",
  "been",
  "were",
  "they",
  "them",
  "about",
  "into",
  "please",
  // Malay, the same kind of words: they match without meaning the draft used the sentence.
  "dengan",
  "untuk",
  "yang",
  "akan",
  "kepada",
  "adalah",
  "telah",
  "boleh",
  "dalam",
  "pada",
  "atau",
  "juga",
  "sila",
  "kami",
  "anda",
  "mereka",
  "tersebut",
  "terima",
  "kasih",
]);

export type Segment = { text: string; isUsed: boolean };

// Chinese has no spaces between words, so a run of characters is compared in overlapping pairs.
function characterPairs(run: string): string[] {
  const characters = [...run];
  return characters.slice(1).map((character, index) => characters[index] + character);
}

function contentWords(text: string): Set<string> {
  const words = text.toLowerCase().match(WORD) ?? [];
  return new Set(
    words.flatMap((word) => {
      if (HAN.test(word)) return characterPairs(word);
      return word.length >= MIN_WORD_LENGTH && !COMMON.has(word) ? [word] : [];
    }),
  );
}

export function highlightUsed(excerpt: string, draft: string): Segment[] {
  const drafted = contentWords(draft);
  return excerpt.split(SENTENCE_BREAK).map((sentence) => {
    const shared = [...contentWords(sentence)].filter((word) => drafted.has(word));
    return { text: sentence, isUsed: shared.length >= MIN_SHARED_WORDS };
  });
}
