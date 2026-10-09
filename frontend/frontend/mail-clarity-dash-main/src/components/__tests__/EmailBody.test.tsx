// @vitest-environment jsdom
import { fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import EmailBody from "../EmailBody";

// jsdom has no layout, so the content's height is whatever the test says it is.
function contentHeight(px: number) {
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(px);
}

afterEach(() => vi.restoreAllMocks());

const email = emailFixture({ id: "e1", body: "First line.\nSecond line.\nThird line." });

describe("a long email body", () => {
  test("is clipped with a button that expands and collapses it", () => {
    contentHeight(600);
    renderWithProviders(<EmailBody email={email} />);
    const toggle = screen.getByRole("button", { name: "Show full email" });
    const box = document.getElementById(toggle.getAttribute("aria-controls") ?? "");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(box?.className).toContain("max-h-32");

    fireEvent.click(toggle);
    expect(toggle.textContent).toBe("Show less");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(box?.className).not.toContain("max-h-32");
  });

  test("keeps the same body element through collapse and expand", () => {
    contentHeight(600);
    renderWithProviders(<EmailBody email={email} />);
    const before = screen.getByText(/First line\./);
    const toggle = screen.getByRole("button", { name: "Show full email" });
    fireEvent.click(toggle);
    fireEvent.click(toggle);
    expect(screen.getByText(/First line\./)).toBe(before);
  });
});

describe("a short email body", () => {
  test("renders in full with no button", () => {
    contentHeight(40);
    renderWithProviders(<EmailBody email={email} />);
    expect(screen.getByText(/First line\./)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Show full email|Show less/ })).toBeNull();
  });
});
