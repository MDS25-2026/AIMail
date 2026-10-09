import { describe, expect, test } from "vitest";

import { parseInlineTokens } from "../../components/FormattedChatMessage";

describe("parseInlineTokens", () => {
  test("parses bold tokens into React elements", () => {
    const nodes = parseInlineTokens("Deadline is **October 8, 2026** today.");
    expect(nodes.length).toBe(3);
    expect(nodes[0]).toBe("Deadline is ");
    expect((nodes[1] as any).type).toBe("strong");
    expect((nodes[1] as any).props.children).toBe("October 8, 2026");
    expect(nodes[2]).toBe(" today.");
  });

  test("parses inline code tokens into code element", () => {
    const nodes = parseInlineTokens("See branch `feat/144-search-qa`.");
    expect(nodes.length).toBe(3);
    expect(nodes[0]).toBe("See branch ");
    expect((nodes[1] as any).type).toBe("code");
    expect((nodes[1] as any).props.children).toBe("feat/144-search-qa");
    expect(nodes[2]).toBe(".");
  });

  test("parses markdown links into anchor element", () => {
    const nodes = parseInlineTokens("Check [API Docs](https://example.com/api) here.");
    expect(nodes.length).toBe(3);
    expect((nodes[1] as any).type).toBe("a");
    expect((nodes[1] as any).props.href).toBe("https://example.com/api");
    expect((nodes[1] as any).props.children).toBe("API Docs");
  });
});
