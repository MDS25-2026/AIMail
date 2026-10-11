// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { useDraftWorkflow } from "../../lib/useDraftWorkflow";
import { emailFixture } from "../../test/emailFixture";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import type { Email } from "../../types/email";
import DraftReplyEditor from "../DraftReplyEditor";
import TemplatePicker from "../TemplatePicker";

const { t } = createI18n(Language.English);

const TEMPLATES = [
  { id: "a", title: "Thanks", body: "Thanks!", language: "en", triggerKeywords: [] },
  {
    id: "b",
    title: "Invoice details",
    body: "Hi {{name}}",
    language: "en",
    triggerKeywords: ["invoice"],
  },
];

const EMAIL = emailFixture({
  id: "e",
  draftReply: "AI draft",
  suggestedTemplateId: "b",
  details: [{ placeholder: "[PERSON_3]", value: "Aisyah Rahman", kind: "PERSON" }],
});

function Harness({ email }: { email: Email }) {
  const workflow = useDraftWorkflow(email);
  return (
    <>
      <DraftReplyEditor email={email} workflow={workflow} />
      <TemplatePicker email={email} workflow={workflow} />
    </>
  );
}

const editor = () => screen.getByRole<HTMLTextAreaElement>("textbox", { name: t("draft.title") });

test("the suggested template is offered and inserting puts it in the editor with the real name", async () => {
  const calls = stubFetch({
    "GET /templates": { body: TEMPLATES },
    "POST /templates/b/fill": { body: { text: "Hi [PERSON_3]" } },
  });
  renderWithProviders(<Harness email={EMAIL} />);
  expect(
    await screen.findByText(t("templates.suggested", { title: "Invoice details" })),
  ).toBeTruthy();
  await userEvent.click(screen.getByRole("button", { name: t("templates.insert") }));
  await vi.waitFor(() => expect(editor().value).toBe("Hi Aisyah Rahman"));
  expect(calls.find((call) => call.path === "/templates/b/fill")?.body).toEqual({ emailId: "e" });
});

test("inserting over typed changes asks first and keeps them until the reader agrees", async () => {
  stubFetch({ "GET /templates": { body: TEMPLATES } });
  renderWithProviders(<Harness email={EMAIL} />);
  await screen.findByRole("button", { name: t("templates.insert") });
  await userEvent.type(editor(), " plus mine");
  await userEvent.click(screen.getByRole("button", { name: t("templates.insert") }));
  expect(screen.getByText(t("templates.replaceEdits"))).toBeTruthy();
  expect(editor().value).toBe("AI draft plus mine");
});

test("nothing shows until the reader has saved a template", async () => {
  const calls = stubFetch({ "GET /templates": { body: [] } });
  renderWithProviders(<Harness email={EMAIL} />);
  await vi.waitFor(() => expect(calls.some((call) => call.path === "/templates")).toBe(true));
  expect(screen.queryByRole("button", { name: t("templates.insert") })).toBeNull();
});
