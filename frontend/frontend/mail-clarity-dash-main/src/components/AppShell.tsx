import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import SideNav from "./SideNav";

/** App chrome shared by every dashboard route: brand header plus the nav rail. */
export default function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    // relative: the containing block for anything absolutely positioned below (sr-only text),
    // so none of it can position against the page and stretch it past the viewport (#96).
    <div className="relative flex h-dvh flex-col overflow-hidden bg-app">
      <header className="flex items-center justify-between border-b border-line bg-surface px-6 py-3">
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-semibold tracking-tight text-fg">{t("app.name")}</span>
          <span className="text-xs text-fg-subtle">{t("app.tagline")}</span>
        </div>
        <Link to="/extension" className="text-sm font-medium text-brand hover:text-brand-strong">
          {t("app.extensionPreview")}
        </Link>
      </header>

      <main className="flex min-h-0 flex-1">
        <SideNav />
        {children}
      </main>
    </div>
  );
}
