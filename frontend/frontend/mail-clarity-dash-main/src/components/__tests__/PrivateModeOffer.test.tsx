// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch, writes } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import PrivateModeOffer from "../PrivateModeOffer";

const { t } = createI18n(Language.English);
const offered = {
  available: true,
  enabled: false,
  isDecided: false,
  model: "gemma4:e2b",
  search: true,
};

test("the offer makes the agreed claim, and Not now puts it away for good", async () => {
  const calls = stubFetch({
    "GET /settings/private-mode": { body: offered },
    "POST /settings/private-mode/not-now": { status: 204 },
  });
  renderWithProviders(<PrivateModeOffer />);
  expect(await screen.findByText(/Never sent to Google or Anthropic/)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: t("privateOffer.notNow") }));
  await vi.waitFor(() => expect(screen.queryByText(t("privateOffer.title"))).toBeNull());
  expect(writes(calls).map((call) => call.path)).toEqual(["/settings/private-mode/not-now"]);
});

test.each([
  ["the company has not set it up", { ...offered, available: false }],
  ["it is already on", { ...offered, enabled: true }],
  ["the user already answered", { ...offered, isDecided: true }],
])("there is no offer when %s", async (_case, mode) => {
  const calls = stubFetch({ "GET /settings/private-mode": { body: mode } });
  renderWithProviders(<PrivateModeOffer />);
  await vi.waitFor(() => expect(calls.length).toBe(1));
  expect(screen.queryByText(t("privateOffer.title"))).toBeNull();
});
