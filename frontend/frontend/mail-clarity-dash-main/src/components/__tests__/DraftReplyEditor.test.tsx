// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { stubFetch } from "../../test/fetchStub";
import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import { useDraftWorkflow } from "../../lib/useDraftWorkflow";
import { ReviewCode, type Email } from "../../types/email";
import DraftReplyEditor from "../DraftReplyEditor";

function Editor({ email }: { email: Email }) {
  return <DraftReplyEditor email={email} workflow={useDraftWorkflow(email)} />;
}

const first = emailFixture({ id: "d1", draftReply: "Thanks, I will reply soon." });
const second = emailFixture({ id: "d2", draftReply: "Noted, see you then." });

const draftButton = () => screen.getByRole("button", { name: "Draft" });
const changesButton = () => screen.getByRole("button", { name: "Changes" });

describe("the Changes view (#149)", () => {
  test("marks the reader's edits against the AI draft, read-only", () => {
    stubFetch({});
    renderWithProviders(<Editor email={first} />);
    expect(draftButton().getAttribute("aria-pressed")).toBe("true");
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "Thanks, I will reply tomorrow." },
    });

    fireEvent.click(changesButton());
    expect(changesButton().getAttribute("aria-pressed")).toBe("true");
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByText("Your edits to the AI draft")).toBeTruthy();
    expect(document.querySelector("ins")?.textContent).toBe("added: tomorrow");
    expect(document.querySelector("del")?.textContent).toBe("removed: soon");
  });

  test("says so when nothing changed", () => {
    stubFetch({});
    renderWithProviders(<Editor email={first} />);
    fireEvent.click(changesButton());
    expect(screen.getByText("No changes from the AI draft yet.")).toBeTruthy();
    expect(document.querySelector("ins, del")).toBeNull();
  });

  test("back on Draft, the text box holds the same edits", () => {
    stubFetch({});
    renderWithProviders(<Editor email={first} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "My own words." } });
    fireEvent.click(changesButton());
    fireEvent.click(draftButton());
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("My own words.");
  });

  test("opening another email starts on Draft", () => {
    stubFetch({});
    const { rerender } = renderWithProviders(<Editor email={first} />);
    fireEvent.click(changesButton());
    rerender(<Editor email={second} />);
    expect(draftButton().getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("textbox")).toBeTruthy();
  });
});

describe("the AI check (plain-wording-and-polish.md)", () => {
  test("a confident draft with a reason to check says so, and never 'passed'", () => {
    stubFetch({});
    const flagged = emailFixture({
      id: "d3",
      criticConfidence: 0.95,
      reviewReasons: [{ code: ReviewCode.NotGrounded, items: [] }],
    });
    renderWithProviders(<Editor email={flagged} />);
    expect(screen.getByText("AI check: review suggested · 95% sure")).toBeTruthy();
    expect(screen.queryByText(/AI check passed/)).toBeNull();
    expect(
      screen.getByText("No company document matched, so the reply isn't backed by your policies."),
    ).toBeTruthy();
  });

  test("a draft with nothing to check passes, with no reason list", () => {
    stubFetch({});
    renderWithProviders(
      <Editor email={emailFixture({ id: "d4", criticConfidence: 0.92, reviewReasons: [] })} />,
    );
    expect(screen.getByText("AI check passed · 92% sure")).toBeTruthy();
    expect(screen.queryByText("Why to check this draft")).toBeNull();
  });
});

describe("the AI check badge (#241)", () => {
  test("is not shown when there is no draft, as for an automated email", () => {
    stubFetch({});
    const automated = emailFixture({
      id: "auto",
      isAutomated: true,
      draftReply: "",
      criticConfidence: 0,
      reviewReasons: [],
    });
    renderWithProviders(<Editor email={automated} />);
    expect(screen.queryByText(/AI check/)).toBeNull();
  });

  test("is shown with its score when there is a draft", () => {
    stubFetch({});
    renderWithProviders(<Editor email={emailFixture({ id: "d3", criticConfidence: 0.93 })} />);
    expect(screen.getByText("AI check passed · 93% sure")).toBeTruthy();
  });
});
