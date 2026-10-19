import { describe, expect, test } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { AuthStatus, MaskingStatus } from "../../types/email";
import { isPendingDraft } from "../drafts";

// emailFixture is a complete, unsent email with a draft: the case that is listed.
describe("which emails the Drafts page lists (specs/features/drafts-page.md)", () => {
  test("a written, unsent draft is listed", () => {
    expect(isPendingDraft(emailFixture())).toBe(true);
  });

  test.each([
    ["it was sent", { sentAt: "2026-10-09T09:00:00Z" }],
    ["the reader already replied from Gmail", { isAnswered: true }],
    ["it is scheduled to send later", { scheduledFor: "2026-10-20T01:00:00Z" }],
    ["no draft was written", { draftReply: "" }],
    ["the draft is only spaces", { draftReply: "   " }],
    ["its draft is still being written", { isDrafting: true }],
    ["the sender failed its checks", { authStatus: AuthStatus.SpoofDetected }],
    ["masking is pending", { masking: MaskingStatus.Pending }],
    ["masking was abandoned", { masking: MaskingStatus.Abandoned }],
  ])("not listed when %s", (_case, overrides) => {
    expect(isPendingDraft(emailFixture(overrides))).toBe(false);
  });

  test("a sender the reader confirmed is listed again", () => {
    expect(isPendingDraft(emailFixture({ authStatus: AuthStatus.SenderConfirmed }))).toBe(true);
  });
});
