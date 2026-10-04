import { describe, expect, test } from "vitest";

import {
  type AttributeNode,
  FORBIDDEN_TAGS,
  blockRemoteImages,
  openLinksInNewTab,
} from "../sanitizeEmail";

function element(
  tagName: string,
  attributes: Record<string, string>,
): AttributeNode & { attrs: Record<string, string> } {
  const attrs = { ...attributes };
  return {
    attrs,
    tagName,
    getAttribute: (name: string) => attrs[name] ?? null,
    setAttribute: (name: string, value: string) => {
      attrs[name] = value;
    },
    removeAttribute: (name: string) => {
      delete attrs[name];
    },
  };
}

describe("remote images", () => {
  test("a tracking pixel's remote source is removed", () => {
    const img = element("IMG", { src: "https://track.example.com/open.gif?u=1", alt: "" });
    expect(blockRemoteImages(img)).toBe(true);
    expect(img.attrs.src).toBeUndefined();
  });

  test("protocol-relative sources, srcset entries, background attributes and CSS urls are all caught", () => {
    expect(blockRemoteImages(element("IMG", { src: "//cdn.example.com/a.png" }))).toBe(true);
    expect(blockRemoteImages(element("IMG", { srcset: "a.png 1x, https://x.com/b.png 2x" }))).toBe(
      true,
    );
    expect(blockRemoteImages(element("TD", { background: "http://x.com/bg.png" }))).toBe(true);
    expect(
      blockRemoteImages(element("DIV", { style: "background:url('https://x.com/p.gif')" })),
    ).toBe(true);
  });

  test("inline images and ordinary styles are left alone", () => {
    const inline = element("IMG", { src: "data:image/png;base64,AAAA" });
    expect(blockRemoteImages(inline)).toBe(false);
    expect(inline.attrs.src).toBe("data:image/png;base64,AAAA");
    expect(blockRemoteImages(element("P", { style: "color: red" }))).toBe(false);
  });
});

describe("links", () => {
  test("a link opens in a new tab without giving the page a handle on ours", () => {
    const link = element("A", { href: "https://example.com" });
    openLinksInNewTab(link);
    expect(link.attrs).toMatchObject({ target: "_blank", rel: "noopener noreferrer" });
  });

  test("an anchor without a link is untouched", () => {
    const anchor = element("A", { name: "top" });
    openLinksInNewTab(anchor);
    expect(anchor.attrs.target).toBeUndefined();
  });
});

test("every form control is forbidden, so no email can draw a sign-in box", () => {
  expect(FORBIDDEN_TAGS).toEqual(
    expect.arrayContaining(["form", "input", "button", "select", "textarea"]),
  );
});
