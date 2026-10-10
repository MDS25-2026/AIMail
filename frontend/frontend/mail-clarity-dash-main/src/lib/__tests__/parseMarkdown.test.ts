import type { ReactElement } from "react";
import { describe, expect, test } from "vitest";

import { parseInlineTokens } from "../parseMarkdown";

describe("parseInlineTokens", () => {
  test("parses bold tokens into React elements", () => {
    const nodes = parseInlineTokens("Deadline is **October 8, 2026** today.");
    expect(nodes.length).toBe(3);
    expect(nodes[0]).toBe("Deadline is ");
    const el = nodes[1] as ReactElement<{ children?: string }>;
    expect(el.type).toBe("strong");
    expect(el.props.children).toBe("October 8, 2026");
    expect(nodes[2]).toBe(" today.");
  });

  test("parses inline code tokens into code element", () => {
    const nodes = parseInlineTokens("See branch `feat/144-search-qa`.");
    expect(nodes.length).toBe(3);
    expect(nodes[0]).toBe("See branch ");
    const el = nodes[1] as ReactElement<{ children?: string }>;
    expect(el.type).toBe("code");
    expect(el.props.children).toBe("feat/144-search-qa");
    expect(nodes[2]).toBe(".");
  });

  test("parses markdown links into anchor element", () => {
    const nodes = parseInlineTokens("Check [API Docs](https://example.com/api) here.");
    expect(nodes.length).toBe(3);
    const el = nodes[1] as ReactElement<{ href?: string; children?: string }>;
    expect(el.type).toBe("a");
    expect(el.props.href).toBe("https://example.com/api");
    expect(el.props.children).toBe("API Docs");
  });
});
