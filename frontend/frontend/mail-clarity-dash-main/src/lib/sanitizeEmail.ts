import DOMPurify from "dompurify";

// Form controls let an email draw a working fake sign-in box inside our own UI.
export const FORBIDDEN_TAGS = ["form", "input", "button", "select", "option", "textarea"];

const REMOTE_URL = /^\s*(?:https?:)?\/\//i;
const REMOTE_CSS_URL = /url\(\s*['"]?\s*(?:https?:)?\/\//i;
const IMAGE_ATTRIBUTES = ["src", "srcset", "background"] as const;

/** The slice of a DOM element the hooks touch, so they can be tested without a browser DOM. */
export type AttributeNode = Pick<
  Element,
  "tagName" | "getAttribute" | "setAttribute" | "removeAttribute"
>;

/** Remote images report the open and the reader's IP to the sender. Returns whether one was removed. */
export function blockRemoteImages(node: AttributeNode): boolean {
  let isBlocked = false;
  for (const name of IMAGE_ATTRIBUTES) {
    const value = node.getAttribute(name);
    if (value === null) continue;
    const isRemote =
      name === "srcset"
        ? value.split(",").some((part) => REMOTE_URL.test(part))
        : REMOTE_URL.test(value);
    if (!isRemote) continue;
    node.removeAttribute(name);
    isBlocked = true;
  }
  const style = node.getAttribute("style");
  if (style !== null && REMOTE_CSS_URL.test(style)) {
    node.removeAttribute("style");
    isBlocked = true;
  }
  return isBlocked;
}

/** A link followed in place would navigate away from the dashboard and lose unsaved draft edits. */
export function openLinksInNewTab(node: AttributeNode): void {
  if (node.tagName !== "A" || node.getAttribute("href") === null) return;
  node.setAttribute("target", "_blank");
  node.setAttribute("rel", "noopener noreferrer");
}

export type SanitizedEmail = { html: string; blockedImages: number };

/** Untrusted email HTML made safe to render: no scripts or forms, links in a new tab, remote images off unless allowed. */
export function sanitizeEmailHtml(html: string, isAllowingRemoteImages: boolean): SanitizedEmail {
  let blockedImages = 0;
  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    openLinksInNewTab(node);
    if (!isAllowingRemoteImages && blockRemoteImages(node)) blockedImages += 1;
  });
  try {
    const clean = DOMPurify.sanitize(html, { FORBID_TAGS: FORBIDDEN_TAGS, ADD_ATTR: ["target"] });
    return { html: clean, blockedImages };
  } finally {
    DOMPurify.removeHook("afterSanitizeAttributes");
  }
}
