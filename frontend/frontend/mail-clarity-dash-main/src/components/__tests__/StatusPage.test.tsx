// @vitest-environment jsdom
import { screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { expect, test, vi } from "vitest";

import { createI18n } from "../../lib/i18n";
import { Language } from "../../lib/preferences";
import { stubFetch } from "../../test/fetchStub";
import { renderWithProviders } from "../../test/render";
import StatusPage from "../StatusPage";

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  Link: ({ children }: { children: ReactNode }) => <a href="/">{children}</a>,
}));

const { t } = createI18n(Language.English);

type Part = "dashboard" | "backend" | "database" | "masking" | "drafting" | "listener";

const row = (part: Part) => screen.getByText(t(`serviceStatus.parts.${part}`)).closest("li");

test("each part shows its state in words, and one failure leaves the rest as they are", async () => {
  stubFetch({
    "GET /service-status": {
      body: {
        checkedAt: "2026-10-12T10:00:00Z",
        parts: {
          backend: "ok",
          database: "ok",
          masking: "down",
          drafting: "ok",
          listener: "degraded",
        },
      },
    },
  });
  renderWithProviders(<StatusPage />);
  await screen.findAllByText(t("serviceStatus.states.down"));
  expect(row("masking")?.textContent).toContain(t("serviceStatus.states.down"));
  expect(row("listener")?.textContent).toContain(t("serviceStatus.states.degraded"));
  expect(row("database")?.textContent).toContain(t("serviceStatus.states.ok"));
  expect(row("dashboard")?.textContent).toContain(t("serviceStatus.states.ok"));
});

test("with no answer from the server, every server part reads not working but the dashboard works", async () => {
  stubFetch({ "GET /service-status": { status: 503 } });
  renderWithProviders(<StatusPage />);
  await screen.findAllByText(t("serviceStatus.states.down"));
  for (const part of ["backend", "database", "masking", "drafting", "listener"] as const) {
    expect(row(part)?.textContent).toContain(t("serviceStatus.states.down"));
  }
  expect(row("dashboard")?.textContent).toContain(t("serviceStatus.states.ok"));
});
