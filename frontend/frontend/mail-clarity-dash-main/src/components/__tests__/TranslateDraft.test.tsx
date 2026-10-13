// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { useDraftWorkflow } from "../../lib/useDraftWorkflow";
import { emailFixture } from "../../test/emailFixture";
import { stubFetch, writes } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import type { Email } from "../../types/email";
import TranslateDraft from "../TranslateDraft";

const { t } = createI18n(Language.English);
const MALAY = "Terima kasih, saya akan hantar invois itu kepada anda esok dan sila maklumkan.";

function Harness({ email }: { email: Email }) {
  const workflow = useDraftWorkflow(email);
  return (
    <>
      <TranslateDraft email={email} workflow={workflow} />
      <p data-testid="draft">{workflow.draft}</p>
    </>
  );
}

const englishEmail = (draftReply: string) =>
  emailFixture({
    body: "Could you please send the invoice for this order? Thank you, we will pay this week.",
    draftReply,
  });

test("a reply written in Malay to an English email is translated, with your words kept to go back to", async () => {
  const calls = stubFetch({
    "POST /emails/email-1/translate-draft": {
      body: {
        language: "en",
        text: "Thanks, I will send you the invoice tomorrow; please let me know.",
      },
    },
  });
  renderWithProviders(<Harness email={englishEmail(MALAY)} />);
  await userEvent.click(
    screen.getByRole("button", {
      name: t("writeInMine.translateTo", { language: t("languages.en") }),
    }),
  );
  await vi.waitFor(() =>
    expect(screen.getByTestId("draft").textContent).toContain("I will send you the invoice"),
  );
  expect(writes(calls)[0].body).toEqual({ text: MALAY });
  expect(screen.getByText(MALAY)).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: t("writeInMine.undo") }));
  expect(screen.getByTestId("draft").textContent).toBe(MALAY);
});

test("a reply already in the email's language is not offered a translation", () => {
  renderWithProviders(
    <Harness email={englishEmail("Thanks, I will send the invoice to you this week.")} />,
  );
  expect(screen.queryByRole("button", { name: /Translate my reply/ })).toBeNull();
});
