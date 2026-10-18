// @vitest-environment jsdom
import { fireEvent, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import InboxList from "../InboxList";

const emails = [
  emailFixture({ id: "person", threadId: "t1", subject: "Quote for November" }),
  emailFixture({
    id: "news",
    threadId: "t2",
    subject: "October newsletter",
    isAutomated: true,
    isRead: false,
  }),
];

function renderList(view: "primary" | "updates", onViewChange = vi.fn(), hasOlder = false) {
  renderWithProviders(
    <InboxList
      emails={emails}
      selectedEmailId={null}
      onSelectEmail={vi.fn()}
      view={view}
      onViewChange={onViewChange}
      hasOlder={hasOlder}
    />,
  );
  return onViewChange;
}

test("Primary lists mail from people only, and Updates shows its unread count", () => {
  renderList("primary");
  expect(screen.getByText("Quote for November")).toBeTruthy();
  expect(screen.queryByText("October newsletter")).toBeNull();
  const updates = screen.getByRole("tab", { name: /Updates/ });
  expect(within(updates).getByText("1 unread")).toBeTruthy();
  expect(screen.getByRole("tab", { name: "Primary" }).getAttribute("aria-selected")).toBe("true");
});

test("Updates lists newsletters and says AIMail doesn't draft for them", () => {
  renderList("updates");
  expect(screen.getByText("October newsletter")).toBeTruthy();
  expect(screen.queryByText("Quote for November")).toBeNull();
  expect(screen.getByText(/doesn't draft replies/)).toBeTruthy();
});

test("clicking a tab or pressing the arrow keys switches the view", () => {
  const onViewChange = renderList("primary");
  fireEvent.click(screen.getByRole("tab", { name: /Updates/ }));
  expect(onViewChange).toHaveBeenLastCalledWith("updates");
  fireEvent.keyDown(screen.getByRole("tab", { name: "Primary" }), { key: "ArrowRight" });
  expect(onViewChange).toHaveBeenLastCalledWith("updates");
});

test("an empty tab says what would be there", () => {
  renderWithProviders(
    <InboxList
      emails={[emails[0]]}
      selectedEmailId={null}
      onSelectEmail={vi.fn()}
      view="updates"
      onViewChange={vi.fn()}
    />,
  );
  expect(screen.getByText("No newsletters or notifications.")).toBeTruthy();
});

test("only the selected tab points at a panel, the one on the page", () => {
  renderList("primary");
  const primary = screen.getByRole("tab", { name: "Primary" });
  expect(primary.getAttribute("aria-controls")).toBe("inbox-panel-primary");
  expect(document.getElementById("inbox-panel-primary")).toBeTruthy();
  expect(screen.getByRole("tab", { name: /Updates/ }).hasAttribute("aria-controls")).toBe(false);
});

test("an empty tab says nothing while older pages may still fill it", () => {
  renderWithProviders(
    <InboxList
      emails={[emails[1]]}
      selectedEmailId={null}
      onSelectEmail={vi.fn()}
      view="primary"
      onViewChange={vi.fn()}
      hasOlder
    />,
  );
  expect(screen.queryByText("Nothing from people right now.")).toBeNull();
});
