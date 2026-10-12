// @vitest-environment jsdom
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test } from "vitest";

import { createI18n } from "../../../lib/i18n";
import { Language } from "../../../lib/preferences";
import { renderWithProviders } from "../../../test/render";
import { FaqSection, PeekSection } from "../LandingSections";
import LivePreview from "../LivePreview";
import { SAMPLE } from "../sample";

const { t } = createI18n(Language.English);
const PERSON = t("landing.preview.placeholders.name");

describe("the landing page", () => {
  test("the live preview shows the real name, hides it for the AI, and puts it back when sent", async () => {
    renderWithProviders(<LivePreview />);
    const preview = screen.getByRole("figure");
    expect(within(preview).getAllByText(SAMPLE.name).length).toBeGreaterThan(0);

    await userEvent.click(
      screen.getByRole("button", { name: t("landing.preview.stages.drafted") }),
    );
    expect(within(preview).queryByText(SAMPLE.name)).toBeNull();
    expect(within(preview).getAllByText(PERSON).length).toBeGreaterThan(1);
    expect(screen.getByText(t("landing.preview.checkBadge"))).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: t("landing.preview.stages.sent") }));
    expect(screen.getByText(t("landing.preview.sentBadge"))).toBeTruthy();
    expect(within(preview).getAllByText(SAMPLE.name).length).toBeGreaterThan(0);
  });

  test("the switch flips one email between the AI's view and the reader's", async () => {
    renderWithProviders(<PeekSection />);
    const toggle = screen.getByRole("switch");
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByText(SAMPLE.phone)).toBeNull();

    await userEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText(SAMPLE.phone)).toBeTruthy();
  });

  test("every question opens to its answer", async () => {
    renderWithProviders(<FaqSection />);
    await userEvent.click(screen.getByText(t("landing.faq.send.q")));
    expect(screen.getByText(t("landing.faq.send.a"))).toBeTruthy();
    expect(screen.getAllByRole("group").length).toBe(5);
  });
});
