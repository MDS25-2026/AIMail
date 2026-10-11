import { describe, expect, test } from "vitest";

import { highlightUsed } from "../highlight";

const POLICY =
  "Refunds are processed within fourteen working days. Gifts above RM500 must be declared. " +
  "Staff may not accept hospitality from vendors during a tender.";

describe("source highlighting", () => {
  test("marks the sentence the draft draws on and only that one", () => {
    const draft = "Your refunds are processed within fourteen working days of approval.";
    const used = highlightUsed(POLICY, draft).filter((segment) => segment.isUsed);
    expect(used.map((segment) => segment.text)).toEqual([
      "Refunds are processed within fourteen working days.",
    ]);
  });

  test("common words alone never make a match", () => {
    const draft = "Please note that this would have been there with them.";
    expect(highlightUsed(POLICY, draft).some((segment) => segment.isUsed)).toBe(false);
  });

  test("keeps every sentence, in order, so the passage reads intact", () => {
    const joined = highlightUsed(POLICY, "")
      .map((segment) => segment.text)
      .join(" ");
    expect(joined).toBe(POLICY);
  });

  test("a Chinese passage is split at its full stops and matched without spaces", () => {
    const policy = "退款将在十四个工作日内处理。超过五百令吉的礼品必须申报。";
    const used = highlightUsed(policy, "您的退款将在十四个工作日内处理，请耐心等候。")
      .filter((segment) => segment.isUsed)
      .map((segment) => segment.text);
    expect(used).toEqual(["退款将在十四个工作日内处理。"]);
  });

  test("a Malay sentence the draft draws on is marked", () => {
    const policy =
      "Bayaran balik akan diproses dalam tempoh empat belas hari bekerja. Hadiah melebihi RM500 mesti diisytiharkan.";
    const used = highlightUsed(
      policy,
      "Bayaran balik anda akan diproses dalam empat belas hari bekerja.",
    )
      .filter((segment) => segment.isUsed)
      .map((segment) => segment.text);
    expect(used).toEqual(["Bayaran balik akan diproses dalam tempoh empat belas hari bekerja."]);
  });

  test("common Malay words alone never make a match", () => {
    const policy = "Hadiah yang akan diberi kepada kakitangan adalah dengan kelulusan untuk semua.";
    const draft = "Dengan untuk yang akan kepada adalah telah boleh.";
    expect(highlightUsed(policy, draft).some((segment) => segment.isUsed)).toBe(false);
  });
});
