// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { ConfirmKind, useDraftWorkflow } from "../../lib/useDraftWorkflow";
import { emailFixture } from "../../test/emailFixture";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import type { Email } from "../../types/email";
import DraftStatus from "../DraftStatus";
import ScheduleBanner from "../ScheduleBanner";

const { t } = createI18n(Language.English);

function Banner({ email }: { email: Email }) {
  return <ScheduleBanner email={email} workflow={useDraftWorkflow(email)} />;
}

test("a send called off because they replied says so", () => {
  stubFetch({});
  renderWithProviders(<Banner email={emailFixture({ scheduleCancelled: "they_replied" })} />);
  expect(screen.getByText(t("schedule.cancelled.they_replied"))).toBeTruthy();
});

test("the quiet-hours question shows both times on their clock and offers to wait", async () => {
  const onSendAtSuggestion = vi.fn();
  renderWithProviders(
    <DraftStatus
      failure={null}
      pendingConfirm={{
        kind: ConfirmKind.QuietHours,
        markerCount: 0,
        quiet: {
          theirNow: new Date("2026-10-07T15:40:00Z"),
          sendAt: new Date("2026-10-08T00:00:00Z"),
          offsetMinutes: 480,
          isTheirTime: true,
        },
      }}
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
      onSendAtSuggestion={onSendAtSuggestion}
      isGenerating={false}
      isLoadFailed={false}
      onRetryLoad={vi.fn()}
    />,
  );
  expect(screen.getByText(/11:40/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: /8:00/ }));
  expect(onSendAtSuggestion).toHaveBeenCalled();
});
