import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { signOut } from "../lib/api";
import { useSession } from "../lib/queries";
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
        <div className="flex items-center gap-4">
          <Link to="/extension" className="text-sm font-medium text-brand hover:text-brand-strong">
            {t("app.extensionPreview")}
          </Link>
          <AccountMenu />
        </div>
      </header>

      <main className="flex min-h-0 flex-1">
        <SideNav />
        {children}
      </main>
    </div>
  );
}

/** The signed-in account and the way out. Signing out clears every cached email from memory too. */
function AccountMenu() {
  const { t } = useTranslation();
  const session = useSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isSigningOut, setIsSigningOut] = useState(false);

  if (!session.data) return null;

  const onSignOut = async () => {
    setIsSigningOut(true);
    try {
      await signOut();
    } finally {
      queryClient.clear();
      void navigate({ to: "/signin" });
    }
  };

  return (
    <div className="flex items-center gap-3 border-l border-line pl-4">
      <span className="max-w-48 truncate text-xs text-fg-muted" title={session.data.email}>
        {session.data.email}
      </span>
      <button
        type="button"
        onClick={() => void onSignOut()}
        disabled={isSigningOut}
        className="text-sm font-medium text-fg-body hover:text-fg disabled:text-fg-subtle"
      >
        {isSigningOut ? t("account.signingOut") : t("account.signOut")}
      </button>
    </div>
  );
}
