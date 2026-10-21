// @vitest-environment jsdom
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { useComposeDraftQuery } from "../../lib/queries";
import { stubFetch, writes, type StubCall } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import { ComposeState, type ComposeDraft } from "../../types/compose";
import ComposeEditor from "../ComposeEditor";

const { t } = createI18n(Language.English);
const PHONE = "012-345 6789";

function composeDraft(overrides: Partial<ComposeDraft> = {}): ComposeDraft {
  return {
    id: "d1",
    to: [],
    cc: [],
    subject: "",
    brief: "",
    body: "",
    tone: "professional",
    state: ComposeState.Draft,
    sources: [],
    reviewReasons: [],
    details: [{ kind: "PHONE", placeholder: "[PHONE_1]", value: PHONE }],
    egress: [],
    updatedAt: "2026-10-21T09:00:00Z",
    ...overrides,
  };
}

/** The editor fed from the draft's query, as the Compose page feeds it. */
function Editor({ id }: { id: string }) {
  const draft = useComposeDraftQuery(id);
  if (!draft.data) return null;
  return <ComposeEditor draft={draft.data} onBack={() => undefined} onDeleted={() => undefined} />;
}

async function renderEditor(draft: ComposeDraft, routes: Parameters<typeof stubFetch>[0] = {}) {
  const calls = stubFetch({ [`GET /compose/${draft.id}`]: { body: draft }, ...routes });
  renderWithProviders(<Editor id={draft.id} />);
  await screen.findByLabelText(t("compose.brief"));
  return calls;
}

const posts = (calls: StubCall[], path: string) => writes(calls).filter((c) => c.path === path);
const sendButton = () => screen.getByRole("button", { name: t("draft.approveSend") });

afterEach(() => vi.useRealTimers());

describe("Write with AIMail", () => {
  test("is disabled with its reason until the brief says something", async () => {
    await renderEditor(composeDraft());
    const write = screen.getByRole("button", { name: t("compose.write") });
    expect(write).toHaveProperty("disabled", true);
    expect(screen.getByText(t("compose.needsBrief"))).toBeTruthy();
  });

  test("fills the body from the brief and lists the documents it used", async () => {
    const written = composeDraft({
      brief: "Remind the team, call me on [PHONE_1]",
      subject: "Leave plans",
      body: "Hi team,\n\nCall me on [PHONE_1].",
      generatedAt: "2026-10-21T09:01:00Z",
      criticConfidence: 0.95,
      sources: [{ label: "Leave policy", excerpt: "Plan leave by 31 October.", score: 0.8 }],
    });
    const calls = await renderEditor(composeDraft(), {
      "POST /compose/d1/write": { body: written },
    });
    fireEvent.change(screen.getByLabelText(t("compose.brief")), {
      target: { value: `Remind the team, call me on ${PHONE}` },
    });
    fireEvent.click(screen.getByRole("button", { name: t("compose.write") }));

    const body = screen.getByLabelText(t("compose.body"));
    await waitFor(() => expect(body).toHaveProperty("value", `Hi team,\n\nCall me on ${PHONE}.`));
    expect(screen.getByDisplayValue("Leave plans")).toBeTruthy();
    expect(screen.getByText("Leave policy")).toBeTruthy();
    // The brief went with its real details; the backend turns them back into placeholders.
    expect(posts(calls, "/compose/d1/write")[0].body).toMatchObject({
      brief: `Remind the team, call me on ${PHONE}`,
    });
    expect(screen.getByRole("button", { name: t("compose.rewrite") })).toBeTruthy();
  });
});

test("Write asks first before replacing a body the user typed, even once it is saved", async () => {
  const typed = "My own words.";
  const calls = await renderEditor(composeDraft({ brief: "Tell them" }), {
    "PATCH /compose/d1": { body: composeDraft({ brief: "Tell them", body: typed }) },
  });
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
  fireEvent.change(screen.getByLabelText(t("compose.body")), { target: { value: typed } });
  await act(() => vi.advanceTimersByTimeAsync(1_500));
  vi.useRealTimers();
  await waitFor(() => expect(posts(calls, "/compose/d1")).toHaveLength(1));

  fireEvent.click(screen.getByRole("button", { name: t("compose.write") }));
  expect(screen.getByText(t("compose.confirm.replaceEdits"))).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: t("draftStatus.keepEditing") }));
  expect(posts(calls, "/compose/d1/write")).toEqual([]);
  expect(screen.getByLabelText(t("compose.body"))).toHaveProperty("value", typed);
});

describe("autosave", () => {
  test("waits for a pause in typing, then saves only what changed", async () => {
    const calls = await renderEditor(composeDraft(), {
      "PATCH /compose/d1": { body: composeDraft({ subject: "Leave" }) },
    });
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const subject = screen.getByLabelText(t("compose.subject"));
    fireEvent.change(subject, { target: { value: "Lea" } });
    await act(() => vi.advanceTimersByTimeAsync(500));
    fireEvent.change(subject, { target: { value: "Leave" } });
    await act(() => vi.advanceTimersByTimeAsync(700));
    expect(writes(calls)).toEqual([]);

    await act(() => vi.advanceTimersByTimeAsync(500));
    vi.useRealTimers();
    await waitFor(() => expect(writes(calls)).toHaveLength(1));
    expect(writes(calls)[0]).toMatchObject({ method: "PATCH", body: { subject: "Leave" } });
    expect(await screen.findByText(t("compose.save.saved"))).toBeTruthy();
  });

  test("an edit still waiting to save is saved before the write starts", async () => {
    const calls = await renderEditor(composeDraft(), {
      "PATCH /compose/d1": { body: composeDraft({ brief: "Tell them" }) },
      "POST /compose/d1/write": { body: composeDraft({ brief: "Tell them", body: "Hello" }) },
    });
    fireEvent.change(screen.getByLabelText(t("compose.brief")), {
      target: { value: "Tell them" },
    });
    fireEvent.click(screen.getByRole("button", { name: t("compose.write") }));
    await screen.findByDisplayValue("Hello");
    expect(writes(calls).map((call) => `${call.method} ${call.path}`)).toEqual([
      "PATCH /compose/d1",
      "POST /compose/d1/write",
    ]);
  });
});

describe("Approve & Send", () => {
  const ready = composeDraft({
    to: ["Aina <aina@x.com>"],
    subject: "Leave",
    body: "Call me on [PHONE_1].",
  });

  test("is blocked, and says why, without a recipient or a subject", async () => {
    const calls = await renderEditor(composeDraft({ body: "Hello" }));
    expect(screen.getByText(t("compose.blocked.noRecipient"))).toBeTruthy();
    expect(sendButton()).toHaveProperty("disabled", true);
    fireEvent.click(sendButton());

    fireEvent.change(screen.getByLabelText(t("compose.to")), { target: { value: "a@x.com," } });
    expect(await screen.findByText(t("compose.blocked.noSubject"))).toBeTruthy();
    expect(sendButton()).toHaveProperty("disabled", true);
    expect(posts(calls, "/compose/d1/send")).toEqual([]);
  });

  test("waits out the undo window, then sends the email with its real details", async () => {
    const calls = await renderEditor(ready, {
      "POST /compose/d1/send": {
        body: { ...ready, state: ComposeState.Sent, sentAt: "2026-10-21T09:05:00Z" },
      },
    });
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
    fireEvent.click(screen.getByRole("checkbox", { name: t("todo.remindMe") }));
    fireEvent.click(sendButton());
    expect(screen.getByText(t("draft.undoSendingIn", { count: 5 }))).toBeTruthy();
    expect(screen.getByLabelText(t("compose.subject"))).toHaveProperty("disabled", true);
    await act(() => vi.advanceTimersByTimeAsync(4_000));
    expect(posts(calls, "/compose/d1/send")).toEqual([]);

    // Past the window, and long enough for the send to land: the query cache tells its
    // subscribers on a timer, which must not be left behind on the fake clock.
    await act(() => vi.advanceTimersByTimeAsync(1_500));
    vi.useRealTimers();
    await waitFor(() => expect(posts(calls, "/compose/d1/send")).toHaveLength(1));
    expect(posts(calls, "/compose/d1/send")[0].body).toEqual({
      to: ["Aina <aina@x.com>"],
      cc: [],
      subject: "Leave",
      body: `Call me on ${PHONE}.`,
      remindIfNoReply: true,
    });
    expect(await screen.findByText(/^Sent /)).toBeTruthy();
  });

  test("leaving the draft during the window sends it at once, as a reply does", async () => {
    const calls = stubFetch({
      "GET /compose/d1": { body: ready },
      "POST /compose/d1/send": { body: { ...ready, state: ComposeState.Sent } },
    });
    const { unmount } = renderWithProviders(<Editor id="d1" />);
    fireEvent.click(await screen.findByRole("button", { name: t("draft.approveSend") }));
    expect(posts(calls, "/compose/d1/send")).toEqual([]);
    unmount();
    await waitFor(() => expect(posts(calls, "/compose/d1/send")).toHaveLength(1));
    expect(posts(calls, "/compose/d1/send")[0].body).toMatchObject({
      body: `Call me on ${PHONE}.`,
    });
  });

  test("Undo in the window means nothing is sent", async () => {
    const calls = await renderEditor(ready);
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval"] });
    fireEvent.click(sendButton());
    fireEvent.click(screen.getByRole("button", { name: t("draft.undo") }));
    await act(() => vi.advanceTimersByTimeAsync(6_000));
    expect(writes(calls)).toEqual([]);
    expect(screen.getByLabelText(t("compose.subject"))).toHaveProperty("disabled", false);
  });

  test("a redaction marker blocks the send, with the reason tied to the button", async () => {
    const calls = await renderEditor(
      composeDraft({ ...ready, body: "Dear [EMAIL_REDACTED], hello." }),
    );
    const reason = screen.getByText(t("compose.blocked.redactionMarkers"));
    expect(sendButton()).toHaveProperty("disabled", true);
    expect(sendButton().getAttribute("aria-describedby")).toBe(reason.id);
    fireEvent.click(sendButton());
    expect(writes(calls)).toEqual([]);
  });

  test("a send that fails after leaving the draft is shown when it is opened again", async () => {
    const calls = stubFetch({
      "GET /compose/d1": { body: ready },
      "POST /compose/d1/send": { status: 502, body: { error: { code: "send_failed" } } },
    });
    const { rerender } = renderWithProviders(<Editor key="first" id="d1" />);
    fireEvent.click(await screen.findByRole("button", { name: t("draft.approveSend") }));
    // Opening another draft: the editor goes, and the send is made at once.
    rerender(<p>elsewhere</p>);
    await waitFor(() => expect(posts(calls, "/compose/d1/send")).toHaveLength(1));
    rerender(<Editor key="again" id="d1" />);
    const alert = await screen.findByText(t("compose.errors.send_failed"));
    expect(alert.closest("[role=alert]")).toBeTruthy();
    expect(screen.queryByText(t("errors.send_failed"))).toBeNull();
  });
});

describe("an email that may have been sent", () => {
  test("is locked, and the user's answer settles it", async () => {
    const unknown = composeDraft({
      to: ["a@x.com"],
      subject: "Leave",
      body: "Hello",
      state: ComposeState.OutcomeUnknown,
    });
    const calls = await renderEditor(unknown, {
      "POST /compose/d1/outcome": {
        body: { ...unknown, state: ComposeState.Sent, sentAt: "2026-10-21T09:05:00Z" },
      },
    });
    expect(screen.getByText(t("compose.outcome.title"))).toBeTruthy();
    expect(screen.getByLabelText(t("compose.body"))).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("button", { name: t("compose.outcome.wasSent") }));
    await screen.findByText(/^Sent /);
    expect(posts(calls, "/compose/d1/outcome")[0].body).toEqual({ outcome: "sent" });
  });

  test("It wasn't sent asks the backend to release it", async () => {
    const unknown = composeDraft({ state: ComposeState.OutcomeUnknown });
    const calls = await renderEditor(unknown, {
      "POST /compose/d1/outcome": { body: { ...unknown, state: ComposeState.Draft } },
    });
    fireEvent.click(screen.getByRole("button", { name: t("compose.outcome.wasNotSent") }));
    await waitFor(() =>
      expect(screen.getByLabelText(t("compose.subject"))).toHaveProperty("disabled", false),
    );
    expect(posts(calls, "/compose/d1/outcome")[0].body).toEqual({ outcome: "not_sent" });
  });
});

test("pasting several addresses makes one chip each, quoted names kept whole", async () => {
  await renderEditor(composeDraft());
  const to = screen.getByLabelText(t("compose.to"));
  fireEvent.paste(to, {
    clipboardData: { getData: () => '"Lim, Daniel" <daniel@x.com>; aina@y.com, nobody' },
  });
  expect(screen.getByText('"Lim, Daniel" <daniel@x.com>')).toBeTruthy();
  expect(screen.getByText("aina@y.com")).toBeTruthy();
  // Kept, but marked in words as well as colour.
  expect(screen.getByText("nobody")).toBeTruthy();
  expect(screen.getByText(t("compose.checkAddress"))).toBeTruthy();
  fireEvent.click(
    screen.getByRole("button", { name: t("compose.removeRecipient", { address: "nobody" }) }),
  );
  expect(screen.queryByText("nobody")).toBeNull();
});

describe("Rewrite", () => {
  const written = composeDraft({
    brief: "Tell them",
    body: "Hi team, call [PHONE_1].",
    generatedAt: "2026-10-21T09:01:00Z",
  });

  test("replaces the AI's own text without asking, also after Hide details is turned on", async () => {
    const calls = await renderEditor(composeDraft({ brief: "Tell them" }), {
      "POST /compose/d1/write": { body: written },
    });
    fireEvent.click(screen.getByRole("button", { name: t("compose.write") }));
    await screen.findByRole("button", { name: t("compose.rewrite") });
    fireEvent.click(screen.getByRole("button", { name: t("details.hide") }));
    fireEvent.click(screen.getByRole("button", { name: t("compose.rewrite") }));
    expect(screen.queryByText(t("compose.confirm.replaceEdits"))).toBeNull();
    await waitFor(() => expect(posts(calls, "/compose/d1/write")).toHaveLength(2));
    fireEvent.click(screen.getByRole("button", { name: t("details.show") }));
  });

  test("asks first after the draft is opened again, since the saved body may be the user's", async () => {
    const edited = { ...written, body: "My own words now." };
    const calls = stubFetch({
      "GET /compose/d1": { body: composeDraft({ brief: "Tell them" }) },
      "POST /compose/d1/write": { body: written },
      "PATCH /compose/d1": { body: edited },
    });
    const { rerender } = renderWithProviders(<Editor key="first" id="d1" />);
    fireEvent.click(await screen.findByRole("button", { name: t("compose.write") }));
    await screen.findByRole("button", { name: t("compose.rewrite") });
    fireEvent.change(screen.getByLabelText(t("compose.body")), {
      target: { value: "My own words now." },
    });
    rerender(<p>elsewhere</p>);
    await waitFor(() => expect(posts(calls, "/compose/d1")).toHaveLength(1));
    rerender(<Editor key="again" id="d1" />);

    fireEvent.click(await screen.findByRole("button", { name: t("compose.rewrite") }));
    expect(screen.getByText(t("compose.confirm.replaceEdits"))).toBeTruthy();
    expect(posts(calls, "/compose/d1/write")).toHaveLength(1);
  });

  test("a draft changed elsewhere meanwhile is refetched, and said in a new email's words", async () => {
    const calls = await renderEditor(composeDraft({ brief: "Tell them" }), {
      "POST /compose/d1/write": { status: 409, body: { error: { code: "conflict" } } },
    });
    fireEvent.click(screen.getByRole("button", { name: t("compose.write") }));
    expect(await screen.findByText(t("compose.errors.conflict"))).toBeTruthy();
    await waitFor(() =>
      expect(
        calls.filter((call) => call.method === "GET" && call.path === "/compose/d1"),
      ).toHaveLength(2),
    );
  });
});

test("the Cc toggle says whether Cc is shown", async () => {
  await renderEditor(composeDraft());
  const toggle = screen.getByRole("button", { name: t("compose.addCc") });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  const hide = screen.getByRole("button", { name: t("compose.hideCc") });
  expect(hide.getAttribute("aria-expanded")).toBe("true");
  expect(document.activeElement).toBe(screen.getByLabelText(t("compose.cc")));
});

test("a paste goes in at the caret, and recipients past the limit stay in the box", async () => {
  const many = Array.from({ length: 19 }, (_, index) => `p${index}@x.com`);
  await renderEditor(composeDraft({ to: many }));
  const to = screen.getByLabelText<HTMLInputElement>(t("compose.to"));
  fireEvent.change(to, { target: { value: "ab" } });
  to.setSelectionRange(1, 1);
  fireEvent.paste(to, { clipboardData: { getData: () => "@x.com, c@y.com\t" } });
  // "a" + paste + "b": the first fits; the rest are over the limit and kept in the box.
  expect(screen.getByText("a@x.com")).toBeTruthy();
  expect(to.value).toBe("c@y.com, b");
  expect(screen.getByText(t("compose.tooManyRecipients", { max: 20 }))).toBeTruthy();
});

test("a failed delete keeps what was typed, and it is saved on leaving", async () => {
  const calls = stubFetch({
    "GET /compose/d1": { body: composeDraft() },
    "DELETE /compose/d1": { status: 500, body: { error: { code: "internal" } } },
    "PATCH /compose/d1": { body: composeDraft({ subject: "Kept" }) },
  });
  const { unmount } = renderWithProviders(<Editor id="d1" />);
  fireEvent.change(await screen.findByLabelText(t("compose.subject")), {
    target: { value: "Kept" },
  });
  fireEvent.click(screen.getByRole("button", { name: t("compose.deleteName") }));
  fireEvent.click(screen.getByRole("button", { name: t("compose.delete") }));
  expect(await screen.findByText(t("errors.internal"))).toBeTruthy();
  unmount();
  const patches = () => calls.filter((call) => call.method === "PATCH");
  await waitFor(() => expect(patches()).toHaveLength(1));
  expect(patches()[0].body).toEqual({ subject: "Kept" });
});
