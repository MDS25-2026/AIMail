import { Language } from "./preferences";

/**
 * Whether an email is worth offering to translate: its main language is not the reader's, or a
 * noticeable part of it is in another language. A heuristic, not a classifier: common words tell
 * English from Malay, and script tells Chinese and other writing systems apart.
 */

const ENGLISH = new Set(
  "the and to of you is for in that this with we your please thank thanks are be have will our on it at as from can if would i".split(
    " ",
  ),
);
const MALAY = new Set(
  "dan yang untuk dengan ini itu tidak anda saya kami ada pada akan dari boleh sila terima kasih adalah dalam kepada telah sudah juga atau bagi oleh mohon".split(
    " ",
  ),
);
const HAN = /\p{Script=Han}/u;
// Letters in a script that is neither Latin nor Han (Tamil, Arabic, Thai...).
const OTHER_SCRIPT = /[^\p{Script=Latin}\p{Script=Han}\P{L}]/u;
const PLACEHOLDERS = /\[[A-Z_]+_?\d*\]|\[Redacted\]/g;
// A second language counts once it has this many common words and this share of them.
const MIN_MIXED_WORDS = 3;
const MIN_MIXED_SHARE = 0.2;

type Counts = { english: number; malay: number; hasHan: boolean; hasOther: boolean };

function count(text: string): Counts {
  const clean = text.replace(PLACEHOLDERS, " ");
  const words = clean.toLowerCase().match(/\p{L}+/gu) ?? [];
  return {
    english: words.filter((word) => ENGLISH.has(word)).length,
    malay: words.filter((word) => MALAY.has(word)).length,
    hasHan: HAN.test(clean),
    hasOther: OTHER_SCRIPT.test(clean),
  };
}

function isMixed(minority: number, total: number): boolean {
  return minority >= MIN_MIXED_WORDS && minority / total >= MIN_MIXED_SHARE;
}

export function needsTranslation(text: string, reader: Language): boolean {
  const { english, malay, hasHan, hasOther } = count(text);
  if (hasOther) return true;
  if (reader === Language.Chinese) return english + malay > 0;
  if (hasHan) return true;
  const total = english + malay;
  if (total === 0) return false; // nothing to judge by, such as a short note or only figures
  const readerCount = reader === Language.Malay ? malay : english;
  return readerCount < total - readerCount || isMixed(total - readerCount, total);
}
