import { describe, expect, test } from "vitest";

import {
  hexFromPermId,
  isConversationUrl,
  isGmailUrl,
  threadIdFromPage,
  threadIdFromUrl,
} from "../../extension/gmailThread";
import { isThreadReport, isWhichThread, MessageType } from "../../extension/messages";

type Fixture = { attributes: Record<string, string>; isShown: boolean };

function page(...elements: Fixture[]) {
  return {
    querySelectorAll: (selector: string) =>
      elements
        .filter((element) => selector.slice(1, -1) in element.attributes)
        .map((element) => ({
          ...element,
          getAttribute: (name: string) => element.attributes[name] ?? null,
        })),
  };
}

const shown = (element: { isShown: boolean }) => element.isShown;
const OPEN = "https://mail.google.com/mail/u/0/#inbox/FMfcgzQbfLhvKXXXXXXXXXXXX";

describe("which Gmail conversation is open", () => {
  test("the visible conversation's thread id is read from the page", () => {
    const gmail = page({
      attributes: { "data-legacy-thread-id": "1a10b0c2d3e4f5a6" },
      isShown: true,
    });
    expect(threadIdFromPage(gmail, OPEN, shown)).toBe("1a10b0c2d3e4f5a6");
  });

  test("a conversation Gmail keeps hidden from earlier is ignored", () => {
    const gmail = page(
      { attributes: { "data-legacy-thread-id": "aaaaaaaaaaaaaaaa" }, isShown: false },
      { attributes: { "data-legacy-thread-id": "bbbbbbbbbbbbbbbb" }, isShown: true },
    );
    expect(threadIdFromPage(gmail, OPEN, shown)).toBe("bbbbbbbbbbbbbbbb");
  });

  test("the inbox list is no conversation, even with an old one still in the page", () => {
    const gmail = page({
      attributes: { "data-legacy-thread-id": "1a10b0c2d3e4f5a6" },
      isShown: true,
    });
    expect(threadIdFromPage(gmail, "https://mail.google.com/mail/u/0/#inbox", shown)).toBeNull();
    expect(threadIdFromPage(gmail, "https://mail.google.com/mail/u/0/#inbox/p2", shown)).toBeNull();
  });

  test("the permanent id is converted from decimal to the API's hex form", () => {
    expect(hexFromPermId("thread-f:1779466812345678901")).toBe(1779466812345678901n.toString(16));
    const gmail = page({
      attributes: { "data-thread-perm-id": "thread-f:1779466812345678901" },
      isShown: true,
    });
    expect(threadIdFromPage(gmail, OPEN, shown)).toBe(1779466812345678901n.toString(16));
  });

  test("an older URL that carries the hex id itself still works", () => {
    const url = "https://mail.google.com/mail/u/0/#label/Work/1a10b0c2d3e4f5a6";
    expect(threadIdFromUrl(url)).toBe("1a10b0c2d3e4f5a6");
    expect(isConversationUrl(url)).toBe(true);
  });

  test("anything malformed reads as no thread rather than a wrong one", () => {
    expect(hexFromPermId("thread-a:12")).toBeNull();
    expect(threadIdFromUrl(OPEN)).toBeNull();
    const gmail = page({ attributes: { "data-legacy-thread-id": "not-hex" }, isShown: true });
    expect(threadIdFromPage(gmail, OPEN, shown)).toBeNull();
  });

  test("only Gmail counts as Gmail", () => {
    expect(isGmailUrl("https://mail.google.com/mail/u/1/#inbox")).toBe(true);
    expect(isGmailUrl("https://mail.google.com.evil.example/")).toBe(false);
    expect(isGmailUrl(undefined)).toBe(false);
  });
});

describe("messages between Gmail and the panel", () => {
  test("a thread report must say which thread, or none", () => {
    expect(isThreadReport({ type: MessageType.ThreadChanged, threadId: "1a10" })).toBe(true);
    expect(isThreadReport({ type: MessageType.ThreadChanged, threadId: null })).toBe(true);
    expect(isThreadReport({ type: MessageType.ThreadChanged })).toBe(false);
    expect(isThreadReport({ type: MessageType.ThreadChanged, threadId: 42 })).toBe(false);
    expect(isThreadReport("aimail:thread-changed")).toBe(false);
  });

  test("anything else asking is not taken for the panel's question", () => {
    expect(isWhichThread({ type: MessageType.WhichThread })).toBe(true);
    expect(isWhichThread({ type: "other" })).toBe(false);
    expect(isWhichThread(null)).toBe(false);
  });
});
