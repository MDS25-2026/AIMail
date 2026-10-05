import { describe, expect, test } from "vitest";

import { needsTranslation } from "../detectLanguage";
import { Language } from "../preferences";

const ENGLISH =
  "Hi, I attended the training last week and would like to claim the fee. Thank you for your help.";
const MALAY =
  "Saya ingin memohon tuntutan untuk kursus itu. Sila hubungi saya dan terima kasih atas bantuan anda.";
const MIXED =
  "Hi, thanks for the update. Saya akan hantar dokumen itu dan sila semak dengan pihak anda.";

describe("offering a translation only when it helps", () => {
  test("an English email is not offered to an English reader", () => {
    expect(needsTranslation(ENGLISH, Language.English)).toBe(false);
  });

  test("a Malay or Chinese email is offered to an English reader", () => {
    expect(needsTranslation(MALAY, Language.English)).toBe(true);
    expect(needsTranslation("您好，我想申请培训费用报销。", Language.English)).toBe(true);
  });

  test("an English email with a real Malay part is offered", () => {
    expect(needsTranslation(MIXED, Language.English)).toBe(true);
  });

  test("a stray foreign word or placeholders do not trigger it", () => {
    expect(needsTranslation(`${ENGLISH} Terima kasih.`, Language.English)).toBe(false);
    expect(
      needsTranslation(
        "Hi [PERSON_1], thank you, see [Redacted] for the details.",
        Language.English,
      ),
    ).toBe(false);
  });

  test("another script, such as Tamil, is always offered", () => {
    expect(needsTranslation(`${ENGLISH} வணக்கம்`, Language.English)).toBe(true);
  });

  test("readers of Malay and Chinese are offered emails not in their language", () => {
    expect(needsTranslation(ENGLISH, Language.Malay)).toBe(true);
    expect(needsTranslation(MALAY, Language.Malay)).toBe(false);
    expect(needsTranslation(ENGLISH, Language.Chinese)).toBe(true);
    expect(needsTranslation("您好，我想申请培训费用报销。", Language.Chinese)).toBe(false);
  });

  test("an email with nothing to judge by is not offered", () => {
    expect(needsTranslation("RM 850, 5 Oct.", Language.English)).toBe(false);
  });
});
