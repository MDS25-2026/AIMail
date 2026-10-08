// Mirrors backend/app/writing_style.py MAX_DESCRIPTION_CHARS.
export const MAX_DESCRIPTION_CHARS = 300;
export const WRITING_STYLE_KEY = ["writing-style"] as const;

/** The description with `phrase` added, or taken out if it is already there. */
export function togglePhrase(text: string, phrase: string): string {
  if (text.includes(phrase))
    return text
      .replace(phrase, "")
      .replace(/\s{2,}/g, " ")
      .trim();
  return [text.trim(), phrase].filter(Boolean).join(" ").slice(0, MAX_DESCRIPTION_CHARS);
}
