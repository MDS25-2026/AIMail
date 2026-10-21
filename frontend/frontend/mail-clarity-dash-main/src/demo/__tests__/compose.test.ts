import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import * as audit from "../../lib/api/audit";
import * as compose from "../../lib/api/compose";
import { ApiError, ApiErrorCode } from "../../lib/api/errors";
import { detailValues, hasMissingDetails, restoreDetails } from "../../lib/details";
import { en } from "../../locales/en";
import { ComposeState } from "../../types/compose";
import { DEMO_COMPOSE_REFINED, DEMO_COMPOSE_WRITTEN } from "../data/compose";
import { DEMO_DOCUMENTS } from "../data/documents";
import { leaveDemo, startDemo } from "../mode";
import { resetDemo } from "../state";

const LEAVE_DRAFT = "demo-compose-leave";

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

async function refusalCode(call: Promise<unknown>): Promise<ApiErrorCode | string> {
  try {
    await settle(call);
    return "answered";
  } catch (error) {
    return error instanceof ApiError ? error.code : String(error);
  }
}

let fetchSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
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
  expect(fetchSpy).not.toHaveBeenCalled();
});

describe("Compose in the demo", () => {
  test("starts with a draft to write and an email sent yesterday", async () => {
    const list = await settle(compose.fetchComposeList());
    expect(list.drafts.map((row) => row.id)).toContain(LEAVE_DRAFT);
    expect(list.sent).toHaveLength(1);
    expect(list.sent[0].state).toBe(ComposeState.Sent);
  });

  test("Write answers a prepared email grounded in a demo document's own words", async () => {
    const written = await settle(compose.writeComposeDraft({ id: LEAVE_DRAFT }));
    expect(written.body).toBe(DEMO_COMPOSE_WRITTEN.body);
    expect(written.subject).toBe(DEMO_COMPOSE_WRITTEN.subject);
    expect(written.generatedAt).toBeTruthy();
    const passages = DEMO_DOCUMENTS.flatMap((document) => document.chunks.map((c) => c.content));
    expect(written.sources?.length).toBeGreaterThan(0);
    for (const source of written.sources ?? []) expect(passages).toContain(source.excerpt);
    expect(written.egress?.map((record) => record.purpose)).toEqual(["search", "draft", "critic"]);
  });

  test("every placeholder in a prepared answer has its detail, so nothing shows unfilled", async () => {
    const { details } = await settle(compose.fetchComposeDraft(LEAVE_DRAFT));
    const values = detailValues(details);
    for (const text of [DEMO_COMPOSE_WRITTEN.body, ...Object.values(DEMO_COMPOSE_REFINED)]) {
      expect(hasMissingDetails(text, values)).toBe(false);
    }
  });

  test("Refine answers its suggestions; a typed instruction is not prepared", async () => {
    await settle(compose.writeComposeDraft({ id: LEAVE_DRAFT }));
    const direct = await settle(
      compose.refineComposeDraft({ id: LEAVE_DRAFT, instruction: en.refine.suggestionDirect }),
    );
    expect(direct.body).toBe(DEMO_COMPOSE_REFINED.direct);
    const typed = compose.refineComposeDraft({ id: LEAVE_DRAFT, instruction: "Make it rhyme" });
    expect(await refusalCode(typed)).toBe(ApiErrorCode.DemoSuggestionsOnly);
  });

  test("a typed value goes back into its placeholder when saved", async () => {
    const saved = await settle(
      compose.saveComposeDraft({ id: LEAVE_DRAFT, fields: { body: "Call me on 012-000 3108." } }),
    );
    expect(saved.body).toBe("Call me on [PHONE_1].");
    expect(restoreDetails(saved.body, detailValues(saved.details))).toBe(
      "Call me on 012-000 3108.",
    );
  });

  test("Send marks the email sent in memory, audited, and locks it", async () => {
    const email = {
      to: ["ops@seribayu.example"],
      cc: [],
      subject: "Leave",
      body: "Hi team, call me on 012-000 3108.",
      remindIfNoReply: false,
    };
    const sent = await settle(compose.sendComposeDraft({ id: LEAVE_DRAFT, email }));
    expect(sent.state).toBe(ComposeState.Sent);
    expect(sent.sentAt).toBeTruthy();
    const list = await settle(compose.fetchComposeList());
    expect(list.sent.map((row) => row.id)).toContain(LEAVE_DRAFT);
    expect(list.drafts.map((row) => row.id)).not.toContain(LEAVE_DRAFT);

    const again = compose.saveComposeDraft({ id: LEAVE_DRAFT, fields: { body: "Changed" } });
    expect(await refusalCode(again)).toBe(ApiErrorCode.AlreadySent);
    const trail = await settle(audit.fetchAuditTrail());
    expect(trail.events.map((event) => event.action)).toContain("compose_sent");
  });

  test("Send refuses an email without a recipient or a subject, as the backend does", async () => {
    const created = await settle(compose.createComposeDraft({ body: "Hello" }));
    const email = { to: [], cc: [], subject: "Hi", body: "Hello", remindIfNoReply: false };
    expect(await refusalCode(compose.sendComposeDraft({ id: created.id, email }))).toBe(
      ApiErrorCode.NoRecipients,
    );
    const noSubject = { ...email, to: ["a@x.com"], subject: "" };
    expect(await refusalCode(compose.sendComposeDraft({ id: created.id, email: noSubject }))).toBe(
      ApiErrorCode.NoSubject,
    );
  });

  test("sending an email already sent answers with it, as the backend does", async () => {
    const email = { to: ["a@x.com"], cc: [], subject: "Hi", body: "Hello", remindIfNoReply: false };
    const first = await settle(compose.sendComposeDraft({ id: LEAVE_DRAFT, email }));
    const again = await settle(
      compose.sendComposeDraft({ id: LEAVE_DRAFT, email: { ...email, body: "Changed" } }),
    );
    expect(again.state).toBe(ComposeState.Sent);
    expect(again.sentAt).toBe(first.sentAt);
    expect(again.body).toBe("Hello");
  });

  test("Send refuses a redaction marker or a placeholder nobody can fill, and changes nothing", async () => {
    const email = { to: ["a@x.com"], cc: [], subject: "Hi", body: "", remindIfNoReply: false };
    const marker = { ...email, body: "Dear [EMAIL_REDACTED]," };
    expect(await refusalCode(compose.sendComposeDraft({ id: LEAVE_DRAFT, email: marker }))).toBe(
      ApiErrorCode.RedactionMarkers,
    );
    const unknown = { ...email, body: "Dear [PERSON_7]," };
    expect(await refusalCode(compose.sendComposeDraft({ id: LEAVE_DRAFT, email: unknown }))).toBe(
      ApiErrorCode.UnresolvedPlaceholders,
    );
    const stored = await settle(compose.fetchComposeDraft(LEAVE_DRAFT));
    expect(stored.state).toBe(ComposeState.Draft);
    expect(stored.body).toBe("");
  });

  test("a new draft is listed, and deleting it removes it", async () => {
    const created = await settle(compose.createComposeDraft({ subject: "Hello" }));
    expect((await settle(compose.fetchComposeList())).drafts[0].id).toBe(created.id);
    await settle(compose.deleteComposeDraft(created.id));
    const list = await settle(compose.fetchComposeList());
    expect(list.drafts.map((row) => row.id)).not.toContain(created.id);
    expect(await refusalCode(compose.fetchComposeDraft(created.id))).toBe(ApiErrorCode.NotFound);
  });
});
