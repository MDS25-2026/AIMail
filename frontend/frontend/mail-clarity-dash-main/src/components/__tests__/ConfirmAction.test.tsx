// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { renderWithProviders } from "../../test/render";
import ConfirmAction, { type ConfirmActionProps } from "../ConfirmAction";

function renderConfirm(overrides: Partial<ConfirmActionProps> = {}) {
  const props: ConfirmActionProps = {
    trigger: "Remove",
    question: "Remove the policy?",
    confirm: "Yes, remove",
    pending: "Removing",
    cancel: "Keep",
    onConfirm: vi.fn(async () => undefined),
    isPending: false,
    error: null,
    ...overrides,
  };
  renderWithProviders(<ConfirmAction {...props} />);
  return props;
}

describe("ConfirmAction", () => {
  test("opening the question puts focus on the safe choice, so Enter never confirms", async () => {
    const props = renderConfirm();
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Keep" }));
    await userEvent.keyboard("{Enter}");
    expect(props.onConfirm).not.toHaveBeenCalled();
  });

  test("cancelling hands focus back to the trigger", async () => {
    renderConfirm();
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Remove" }));
  });

  test("confirming runs the action once and closes the question when it is done", async () => {
    const props = renderConfirm();
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, remove" }));
    expect(props.onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Remove the policy?")).toBeNull();
  });

  test("while the action runs, both choices are disabled and say so", async () => {
    const pending = renderConfirm({ isPending: true });
    await userEvent.click(screen.getByRole("button", { name: pending.trigger }));
    expect(screen.getByRole("button", { name: "Removing" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Keep" }).hasAttribute("disabled")).toBe(true);
  });

  test("a failure stays on the question with its message and a retry", async () => {
    const onConfirm = vi.fn(async () => {
      throw new Error("down");
    });
    renderConfirm({ onConfirm, error: "Couldn't remove it." });
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByRole("alert").textContent).toBe("Couldn't remove it.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Remove the policy?")).toBeTruthy();
  });
});
