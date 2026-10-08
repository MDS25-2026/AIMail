// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { useDraftWorkflow } from "../../lib/useDraftWorkflow";
import { emailFixture } from "../../test/emailFixture";
import { renderWithProviders } from "../../test/render";
import { AuthStatus, MaskingStatus, type Email } from "../../types/email";
import EmailDetailPanel from "../EmailDetailPanel";
import SidePanel from "../SidePanel";

const { t } = createI18n(Language.English);

function InboxPanel({ email }: { email: Email }) {
  return <EmailDetailPanel email={email} workflow={useDraftWorkflow(email)} />;
}

function ExtensionPanel({ email }: { email: Email }) {
  return <SidePanel email={email} workflow={useDraftWorkflow(email)} />;
}

const PANELS = [
  ["inbox panel", InboxPanel],
  ["extension panel", ExtensionPanel],
] as const;

const draftBox = () => screen.queryByRole("textbox", { name: t("draft.title") });

describe.each(PANELS)("%s", (_name, Panel) => {
  test("a spoofed sender shows the sender check with its confirm button, and no draft", () => {
    renderWithProviders(<Panel email={emailFixture({ authStatus: AuthStatus.SpoofDetected })} />);
    expect(screen.getByText(t("security.spoofTitle"))).toBeTruthy();
    expect(screen.getByRole("button", { name: t("security.confirmSender") })).toBeTruthy();
    expect(draftBox()).toBeNull();
    expect(screen.queryByRole("button", { name: t("draft.approveSend") })).toBeNull();
  });

  test("quarantined content shows the quarantine notice, and no draft or summary", () => {
    const email = emailFixture({ masking: MaskingStatus.Pending });
    renderWithProviders(<Panel email={email} />);
    expect(screen.getByText(t("quarantine.title"))).toBeTruthy();
    expect(draftBox()).toBeNull();
    expect(screen.queryByText(email.aiSummary)).toBeNull();
  });

  test("an unverified sender gets the draft with a notice", () => {
    renderWithProviders(<Panel email={emailFixture({ authStatus: AuthStatus.Unverified })} />);
    expect(screen.getByText(t("security.unverified"))).toBeTruthy();
    expect(draftBox()).toBeTruthy();
  });

  test("an email with no sender status at all is treated as unverified", () => {
    renderWithProviders(<Panel email={emailFixture({ authStatus: undefined })} />);
    expect(screen.getByText(t("security.unverified"))).toBeTruthy();
  });

  test("a verified sender gets the draft and no notice", () => {
    renderWithProviders(<Panel email={emailFixture()} />);
    expect(draftBox()).toBeTruthy();
    expect(screen.queryByText(t("security.unverified"))).toBeNull();
    expect(screen.queryByText(t("security.spoofTitle"))).toBeNull();
  });

  test("hidden details in the draft get chips, and the privacy receipt is offered", () => {
    renderWithProviders(<Panel email={emailFixture({ draftReply: "Dear [Redacted], thanks." })} />);
    expect(screen.getByRole("button", { name: t("hiddenDetails.kind.other") })).toBeTruthy();
    expect(screen.getByRole("button", { name: t("receipt.open") })).toBeTruthy();
  });
});
