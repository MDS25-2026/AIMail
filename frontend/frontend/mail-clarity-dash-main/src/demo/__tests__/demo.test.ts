import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import * as audit from "../../lib/api/audit";
import * as documents from "../../lib/api/documents";
import * as emails from "../../lib/api/emails";
import { ApiError, ApiErrorCode } from "../../lib/api/errors";
import * as profile from "../../lib/api/profile";
import * as search from "../../lib/api/search";
import * as session from "../../lib/api/session";
import * as settings from "../../lib/api/settings";
import * as status from "../../lib/api/status";
import * as templates from "../../lib/api/templates";
import * as todo from "../../lib/api/todo";
import { placeholderPattern } from "../../lib/masking";
import { needsTranslation } from "../../lib/detectLanguage";
import { Language } from "../../lib/preferences";
import { en } from "../../locales/en";
import { ms } from "../../locales/ms";
import { zh } from "../../locales/zh";
import { DEMO_ANSWERS, DEMO_CONFIRMED_DRAFTS } from "../data/answers";
import { demoEmails } from "../data/emails";
import { isDemo, leaveDemo, startDemo } from "../mode";
import { resetDemo } from "../request";

const API_MODULES = {
  audit,
  documents,
  emails,
  profile,
  search,
  session,
  settings,
  status,
  templates,
  todo,
};

// One argument that fits every API function: ids for those taking a string, fields for the rest.
const ANY_ARGUMENT = {
  id: "demo-port-klang",
  emailId: "demo-port-klang",
  templateId: "demo-template",
  sentId: "demo-sent",
  draft: "Thanks.",
  sendAt: new Date("2030-01-01T09:00:00Z"),
  until: new Date("2030-01-01T09:00:00Z"),
  text: "Thanks.",
  query: "invoice",
  language: "ms",
};

// The only ways a demo call may fail: never a network error or a sign-out.
const REFUSALS = [ApiErrorCode.NotInDemo, ApiErrorCode.DemoSuggestionsOnly, ApiErrorCode.NotFound];

let fetchSpy: ReturnType<typeof vi.fn>;

/** A demo call's answer, without waiting out its network-like pause in real time. */
async function settle<T>(call: Promise<T>): Promise<T> {
  const outcome = call.then(
    (value) => ({ value }),
    (error: unknown) => ({ error }),
  );
  await vi.advanceTimersByTimeAsync(2_000);
  const settled = await outcome;
  if ("error" in settled) throw settled.error;
  return settled.value;
}

beforeEach(() => {
  // Demo answers wait like a network call; settle() moves the clock past that wait.
  vi.useFakeTimers({ toFake: ["setTimeout"] });
  fetchSpy = vi.fn(() => Promise.reject(new TypeError("the demo reached the network")));
  vi.stubGlobal("fetch", fetchSpy);
  resetDemo();
  startDemo();
});

afterEach(() => {
  leaveDemo();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("demo mode (#227)", () => {
  test("no API call reaches the network: each is answered or refused as not in the demo", async () => {
    const outcomes: string[] = [];
    for (const [file, module] of Object.entries(API_MODULES)) {
      for (const [name, fn] of Object.entries(module)) {
        // The one call allowed out: public and mailbox-free (tested on its own below).
        if (typeof fn !== "function" || fn === status.fetchServiceStatus) continue;
        startDemo(); // Sign out leaves the demo, so each call starts in it again.
        try {
          await settle(
            (fn as (...args: unknown[]) => Promise<unknown>)(ANY_ARGUMENT, ANY_ARGUMENT),
          );
          outcomes.push(`${file}.${name}: answered`);
        } catch (error) {
          const code = error instanceof ApiError ? error.code : String(error);
          outcomes.push(`${file}.${name}: ${code}`);
          expect(REFUSALS).toContain(code);
        }
      }
    }
    expect(outcomes.length).toBeGreaterThan(40);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("the status page asks the real backend, so the demo never reads as every part down", async () => {
    const parts = { backend: "ok", database: "ok", masking: "ok", drafting: "ok", listener: "ok" };
    fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify({ checkedAt: "now", parts })));
    const answer = await status.fetchServiceStatus();
    expect(answer.parts.masking).toBe("ok");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(String(fetchSpy.mock.calls[0][0])).toMatch(/\/service-status$/);
  });

  test("the inbox opens with the demo emails and a demo account", async () => {
    const page = await settle(emails.fetchEmailPage());
    expect(page.emails.map((email) => email.id)).toContain("demo-port-klang");
    expect((await settle(session.fetchSession())).hasMailbox).toBe(true);
  });

  test("Send is pretend: the email is marked sent with the approved text", async () => {
    const sent = await settle(emails.sendEmail("demo-invois", "Terima kasih."));
    expect(sent.sentAt).toBeTruthy();
    expect(sent.draftReply).toBe("Terima kasih.");
    const page = await settle(emails.fetchEmailPage());
    expect(page.emails.find((email) => email.id === "demo-invois")?.sentAt).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  test("a snoozed email leaves the inbox until its time", async () => {
    await settle(
      emails.snoozeEmail({ emailId: "demo-meeting", until: new Date(Date.now() + 60_000) }),
    );
    const page = await settle(emails.fetchEmailPage());
    expect(page.emails.map((email) => email.id)).not.toContain("demo-meeting");
  });

  test("answers are copies, so changing one never changes the demo's mailbox", async () => {
    const first = await settle(emails.fetchEmail("demo-port-klang"));
    first.subject = "changed";
    expect((await settle(emails.fetchEmail("demo-port-klang"))).subject).not.toBe("changed");
  });

  test("Sign out leaves the demo", async () => {
    await settle(session.signOut());
    expect(isDemo()).toBe(false);
  });

  test("every placeholder in the demo has a made-up value behind it", () => {
    for (const email of demoEmails(new Date())) {
      const values = new Set(email.details?.map((detail) => detail.placeholder));
      const text = `${email.subject}\n${email.body}\n${email.draftReply}`;
      for (const [placeholder] of text.matchAll(placeholderPattern())) {
        expect(values, `${email.id} ${placeholder}`).toContain(placeholder);
      }
    }
  });
});

describe("outside demo mode", () => {
  test("calls go to the backend as before", async () => {
    leaveDemo();
    await settle(emails.fetchEmailPage().catch(() => undefined));
    expect(fetchSpy).toHaveBeenCalled();
  });
});

describe("the AI's prepared answers (#227)", () => {
  test("Regenerate in the other tone gives that tone's draft, and back again", async () => {
    const casual = await settle(emails.regenerateEmail("demo-port-klang", "casual"));
    expect(casual.tone).toBe("casual");
    expect(casual.draftReply).toBe(DEMO_ANSWERS["demo-port-klang"].otherTone?.casual);
    const back = await settle(emails.regenerateEmail("demo-port-klang", "professional"));
    expect(back.draftReply).toBe(demoEmails(new Date())[0].draftReply);
  });

  test.each([en, ms, zh])("the refine suggestions work in every language", async (locale) => {
    const direct = await settle(
      emails.refineEmail("demo-invois", locale.refine.suggestionDirect, "", "professional"),
    );
    expect(direct.draftReply).toBe(DEMO_ANSWERS["demo-invois"].direct);
    const deadline = await settle(
      emails.refineEmail("demo-invois", locale.refine.suggestionDeadline, "", "professional"),
    );
    expect(deadline.draftReply).toBe(DEMO_ANSWERS["demo-invois"].deadline);
  });

  test("a typed refine instruction points to the suggestions", async () => {
    await expect(
      settle(emails.refineEmail("demo-invois", "Make it rhyme", "", "professional")),
    ).rejects.toMatchObject({ code: ApiErrorCode.DemoSuggestionsOnly });
  });

  test("Translate answers with the prepared translation", async () => {
    const translation = await settle(emails.translateEmail("demo-meeting", Language.English));
    expect(translation.text).toBe(DEMO_ANSWERS["demo-meeting"].translations.en);
  });

  test("a spoofed sender has no draft until the reader confirms it", async () => {
    const before = await settle(emails.fetchEmail("demo-ceo-transfer"));
    expect(before.draftReply).toBe("");
    const after = await settle(emails.confirmSender("demo-ceo-transfer"));
    expect(after.draftReply).toBe(DEMO_CONFIRMED_DRAFTS["demo-ceo-transfer"]);
  });

  test("every translation the page can offer is prepared", () => {
    for (const email of demoEmails(new Date())) {
      for (const language of Object.values(Language)) {
        if (!needsTranslation(email.body, language)) continue;
        expect(
          DEMO_ANSWERS[email.id]?.translations[language],
          `${email.id} ${language}`,
        ).toBeTruthy();
      }
    }
  });

  test("every email with a draft has both tones and both suggestions prepared", () => {
    for (const email of demoEmails(new Date())) {
      if (!email.draftReply) continue;
      const answers = DEMO_ANSWERS[email.id];
      const otherTone = email.tone === "casual" ? "professional" : "casual";
      expect(answers?.otherTone?.[otherTone], email.id).toBeTruthy();
      expect(answers?.direct, email.id).toBeTruthy();
      expect(answers?.deadline, email.id).toBeTruthy();
    }
  });

  test("every placeholder in a prepared answer has a made-up value behind it", () => {
    for (const email of demoEmails(new Date())) {
      const values = new Set(email.details?.map((detail) => detail.placeholder));
      const answers = DEMO_ANSWERS[email.id];
      const texts = [
        ...Object.values(answers?.otherTone ?? {}),
        answers?.direct ?? "",
        answers?.deadline ?? "",
        ...Object.values(answers?.translations ?? {}),
        DEMO_CONFIRMED_DRAFTS[email.id] ?? "",
      ];
      for (const text of texts) {
        for (const [placeholder] of text.matchAll(placeholderPattern())) {
          expect(values, `${email.id} ${placeholder}`).toContain(placeholder);
        }
      }
    }
  });
});
