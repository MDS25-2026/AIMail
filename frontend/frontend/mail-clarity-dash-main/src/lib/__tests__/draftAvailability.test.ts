import { describe, expect, test } from "vitest";

import { AuthStatus, MaskingStatus } from "../../types/email";
import { DraftAvailability, draftAvailability } from "../draftAvailability";

describe("draftAvailability", () => {
  test.each([
    [MaskingStatus.Pending, AuthStatus.Pass],
    [MaskingStatus.Abandoned, AuthStatus.SpoofDetected],
  ])("withheld content (%s) is quarantined whatever the sender check says", (masking, auth) => {
    expect(draftAvailability({ masking, authStatus: auth })).toBe(DraftAvailability.Quarantined);
  });

  test("a failed sender check holds the draft until the owner confirms", () => {
    const email = { masking: MaskingStatus.Complete, authStatus: AuthStatus.SpoofDetected };
    expect(draftAvailability(email)).toBe(DraftAvailability.NeedsSenderCheck);
  });

  test.each([AuthStatus.Pass, AuthStatus.SenderConfirmed])("%s is ready", (authStatus) => {
    expect(draftAvailability({ masking: MaskingStatus.Complete, authStatus })).toBe(
      DraftAvailability.Ready,
    );
  });

  test("no verdict, or no status at all, reads as unverified, never as pass", () => {
    const unverified = { masking: MaskingStatus.Complete, authStatus: AuthStatus.Unverified };
    expect(draftAvailability(unverified)).toBe(DraftAvailability.ReadyUnverified);
    expect(draftAvailability({ masking: MaskingStatus.Complete })).toBe(
      DraftAvailability.ReadyUnverified,
    );
  });
});
