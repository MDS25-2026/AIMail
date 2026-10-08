import { describe, expect, test } from "vitest";

import { ms } from "../../locales/ms";
import { Page, pageMeta } from "../pageMeta";
import { Language } from "../preferences";

describe("pageMeta", () => {
  test("the title and description are in the reader's language", () => {
    expect(pageMeta(Language.Malay, Page.Audit)).toEqual([
      { title: ms.meta.audit.title },
      { name: "description", content: ms.meta.audit.description },
      { property: "og:title", content: ms.meta.audit.title },
      { property: "og:description", content: ms.meta.audit.description },
    ]);
  });

  test("every page has its own title in every language", () => {
    for (const language of Object.values(Language)) {
      const titles = Object.values(Page).map((page) => pageMeta(language, page)[0]);
      expect(new Set(titles.map((tag) => JSON.stringify(tag))).size).toBe(titles.length);
    }
  });
});
