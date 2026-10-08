import type { TFunction } from "i18next";
import { afterEach, describe, expect, test, vi } from "vitest";

import type { HoldingReplySettings } from "../../types/settings";
import { fetchEmailByThread, regenerateEmail, sendEmail } from "../api/emails";
import { ApiError, ApiErrorCode, errorMessage } from "../api/errors";
import { addStyleExample } from "../api/profile";
import { saveHoldingReplySettings } from "../api/settings";
import { createI18n } from "../i18n";
import { Language } from "../preferences";

function answer(status: number, body: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(body, { status })),
  );
}

const envelope = (code: string) => JSON.stringify({ error: { code, message: "for logs" } });
const t: TFunction = createI18n(Language.English).t;

afterEach(() => vi.unstubAllGlobals());

describe("every failed call is one ApiError carrying the backend's code", () => {
  test("the new envelope names the code", async () => {
    answer(422, envelope("draft_refused"));
    await expect(regenerateEmail("id", "casual")).rejects.toMatchObject({
      status: 422,
      code: ApiErrorCode.DraftRefused,
      endpoint: "POST /emails/id/regenerate",
    });
  });

  test("the old detail shape still works while the backend moves", async () => {
    answer(504, JSON.stringify({ detail: "send_outcome_unknown" }));
    await expect(sendEmail("id", "Thanks.")).rejects.toMatchObject({
      code: ApiErrorCode.SendOutcomeUnknown,
    });
  });

  test("a body that is not JSON is still an ApiError, with no code", async () => {
    answer(500, "Internal Server Error");
    const failure = addStyleExample({ emailId: "e1" });
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({ code: ApiErrorCode.Unknown });
  });

  test("a code this build does not know reads as unknown, not as a crash", async () => {
    answer(400, envelope("brand_new_code"));
    await expect(addStyleExample({ text: "Hi" })).rejects.toMatchObject({
      code: ApiErrorCode.Unknown,
    });
  });

  test("a network failure is an ApiError too, so callers handle one type", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    await expect(sendEmail("id", "Hi")).rejects.toMatchObject({ code: ApiErrorCode.Network });
  });

  test("holding reply validation codes come through by name", async () => {
    answer(422, envelope("leave_needs_dates"));
    const settings = {} as HoldingReplySettings;
    await expect(saveHoldingReplySettings(settings)).rejects.toMatchObject({
      code: ApiErrorCode.LeaveNeedsDates,
    });
  });

  test("a thread AIMail has no email for is null, not an error", async () => {
    answer(404, envelope("not_found"));
    await expect(fetchEmailByThread("thread-1")).resolves.toBeNull();
  });
});

describe("errorMessage", () => {
  test("a known code gets its own message, whatever the caller's fallback", () => {
    const error = new ApiError(409, ApiErrorCode.GoogleAccessExpired, "POST /emails/1/send");
    expect(errorMessage(error, t, "draftStatus.failed.send")).toBe(
      t("errors.google_access_expired"),
    );
  });

  test("an unknown failure gets the caller's fallback", () => {
    const error = new ApiError(500, ApiErrorCode.Unknown, "POST /emails/1/send");
    expect(errorMessage(error, t, "draftStatus.failed.send")).toBe(t("draftStatus.failed.send"));
  });

  test("anything that is not an ApiError gets the generic message, never its own text", () => {
    expect(errorMessage(new Error("stack trace text"), t)).toBe(t("errors.generic"));
  });
});
