import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { SIGN_IN_URL } from "../lib/api/config";
import { signOut } from "../lib/api/session";
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

      <ReconnectBanner />
      <main className="flex min-h-0 flex-1">
        <SideNav />
        {children}
      </main>
    </div>
  );
}

/** Google refused the stored token; until the user signs in again nothing arrives or sends. */
function ReconnectBanner() {
  const { t } = useTranslation();
  const session = useSession();
  if (!session.data?.needsReconnect) return null;
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 border-b border-warning-line bg-warning-soft px-6 py-2 text-sm text-fg"
    >
      <span>{t("reconnect.banner")}</span>
      <a
        href={SIGN_IN_URL}
        className="rounded-md bg-brand px-3 py-1 text-sm font-semibold text-on-brand hover:bg-brand-strong"
      >
        {t("reconnect.signIn")}
      </a>
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
