import { describe, expect, test } from "vitest";

import { splitQuoted } from "../quotedText";

describe("folding the quoted email", () => {
  test("a Gmail reply keeps only the new text, even with hidden details in the header", () => {
    const body =
      "Sounds good, Friday works.\n\nOn Mon, 6 Oct 2026 at 10:00, [PERSON_1] <[EMAIL_1]> wrote:\n> Can we meet?";
    expect(splitQuoted(body)).toEqual({
      own: "Sounds good, Friday works.",
      quoted: "On Mon, 6 Oct 2026 at 10:00, [PERSON_1] <[EMAIL_1]> wrote:\n> Can we meet?",
    });
  });

  test("Outlook's From and Sent block starts the quote", () => {
    const body =
      "Noted, thanks.\n\nFrom: [PERSON_1]\nSent: Monday, 6 October 2026 10:00\nSubject: Quote";
    expect(splitQuoted(body).own).toBe("Noted, thanks.");
  });

  test("a header wrapped over two lines is cut where it starts", () => {
    const body = "Yes.\n\nOn Tue, 7 Oct 2026, [PERSON_1] <[EMAIL_1]>\nwrote:\n> Is it ready?";
    expect(splitQuoted(body)).toEqual({
      own: "Yes.",
      quoted: "On Tue, 7 Oct 2026, [PERSON_1] <[EMAIL_1]>\nwrote:\n> Is it ready?",
    });
  });

  test("Malay and Chinese headers start the quote too", () => {
    expect(splitQuoted("Baik.\nPada Isnin, [PERSON_1] menulis:\n> Boleh?").own).toBe("Baik.");
    expect(splitQuoted("好的。\n[PERSON_1] 写道：\n> 可以吗？").own).toBe("好的。");
  });

  test("an email with no quote, or one that is all quote, is shown whole", () => {
    expect(splitQuoted("Just one line.")).toEqual({ own: "Just one line.", quoted: "" });
    const forward = "> Forwarded text\n> more";
    expect(splitQuoted(forward)).toEqual({ own: forward, quoted: "" });
  });
});
