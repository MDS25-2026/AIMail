// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import TemplatesCard from "../TemplatesCard";

const { t } = createI18n(Language.English);

test("a new template is saved with its trigger words, and the hint names the variables literally", async () => {
  const calls = stubFetch({
    "GET /templates": { body: [] },
    "POST /templates": ({ body }) => ({ status: 201, body: { ...(body as object), id: "n1" } }),
  });
  renderWithProviders(<TemplatesCard />);
  await userEvent.click(await screen.findByRole("button", { name: t("templates.new") }));
  await userEvent.selectOptions(screen.getByLabelText(t("templates.fieldLanguage")), "ms");
  // The braces must survive i18next, which would read {{nama}} as one of its own variables.
  expect(screen.getByText("{{nama}}")).toBeTruthy();
  await userEvent.type(screen.getByLabelText(t("templates.fieldTitle")), "Invois");
  await userEvent.type(screen.getByLabelText(t("templates.fieldBody")), "Salam");
  await userEvent.type(screen.getByLabelText(t("templates.fieldTriggers")), "invois, bayaran");
  await userEvent.click(screen.getByRole("button", { name: t("templates.save") }));
  await vi.waitFor(() =>
    expect(calls.find((call) => call.method === "POST")?.body).toEqual({
      title: "Invois",
      body: "Salam",
      language: "ms",
      triggerKeywords: ["invois", "bayaran"],
    }),
  );
});
