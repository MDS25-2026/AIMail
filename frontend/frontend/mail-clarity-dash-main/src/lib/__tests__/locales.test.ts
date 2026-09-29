import { describe, expect, test } from "vitest";

import { en } from "../../locales/en";
import { ms } from "../../locales/ms";
import { zh } from "../../locales/zh";

type Tree = { readonly [key: string]: string | Tree };

function leaves(tree: Tree, prefix = ""): Map<string, string> {
  const found = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") found.set(path, value);
    else for (const [inner, text] of leaves(value, path)) found.set(inner, text);
  }
  return found;
}

// tsc already proves every key exists; it cannot see inside the strings.
const tokens = (text: string) =>
  [...text.matchAll(/\{\{\w+\}\}|<\/?\w+>/g)].map((m) => m[0]).sort();
const master = leaves(en);

describe.each([
  ["ms", ms],
  ["zh", zh],
])("%s locale", (_name, locale) => {
  const translated = leaves(locale);

  test("keeps every placeholder and tag, so no value or markup silently disappears", () => {
    for (const [key, text] of master) {
      expect(tokens(translated.get(key) ?? ""), key).toEqual(tokens(text));
    }
  });

  test("has no empty strings", () => {
    for (const [key, text] of translated) expect(text.trim(), key).not.toBe("");
  });
});
