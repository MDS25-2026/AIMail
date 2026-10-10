// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { stubFetch } from "../../test/fetchStub";
import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import { useDraftWorkflow } from "../../lib/useDraftWorkflow";
import type { Email } from "../../types/email";
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
