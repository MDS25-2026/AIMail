// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { useDraftWorkflow } from "../../lib/useDraftWorkflow";
import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import type { Email } from "../../types/email";
import EmailDetailPanel from "../EmailDetailPanel";
import PlainBody from "../PlainBody";

const { t } = createI18n(Language.English);

test("the quoted email waits behind a button and the new text shows first", async () => {
  renderWithProviders(
    <PlainBody text={"Friday works.\n\nOn Mon, Aisyah wrote:\n> Can we meet?"} />,
  );
  expect(screen.getByText("Friday works.")).toBeTruthy();
  expect(screen.queryByText(/Can we meet/)).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: t("emailBody.showQuoted") }));
  expect(screen.getByText(/Can we meet/)).toBeTruthy();
});

test("a web address is a link that opens in a new tab, without the bracket after it", () => {
  renderWithProviders(<PlainBody text="Details here (https://aimail.example/terms)." />);
  const link = screen.getByRole("link", { name: "https://aimail.example/terms" });
  expect(link.getAttribute("href")).toBe("https://aimail.example/terms");
  expect(link.getAttribute("target")).toBe("_blank");
  expect(link.getAttribute("rel")).toBe("noopener noreferrer");
});

function Panel({ email }: { email: Email }) {
  return <EmailDetailPanel email={email} workflow={useDraftWorkflow(email)} />;
}

test("an email whose attachment couldn't be read says so", () => {
  renderWithProviders(
    <Panel email={emailFixture({ hasUnreadAttachment: true, threadId: "t1" })} />,
  );
  expect(screen.getByText(t("detail.unreadAttachment"))).toBeTruthy();
});

test("an email with every attachment read says nothing about it", () => {
  renderWithProviders(<Panel email={emailFixture()} />);
  expect(screen.queryByText(t("detail.unreadAttachment"))).toBeNull();
});
