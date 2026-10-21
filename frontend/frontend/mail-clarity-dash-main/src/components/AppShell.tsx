import { Link, useNavigate } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import logoForLight from "../assets/aimail-logo-dark.png";
import logoForDark from "../assets/aimail-logo-light.png";
import { SIGN_IN_URL } from "../lib/api/config";
import { useMailboxEvents, useSession, useSignOut, type LiveState } from "../lib/queries";
import { cn } from "../lib/utils";
import { MAIN_CONTENT_ID } from "../lib/useFocusOnNavigate";
import { useIsReadingEmail } from "../lib/useIsReadingEmail";
import BottomNav from "./BottomNav";
import DemoBanner from "./DemoBanner";
import SideNav from "./SideNav";
import { button } from "./variants";

/** App chrome shared by every dashboard route: brand header plus the nav rail. */
export default function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const isReadingEmail = useIsReadingEmail();
  // One stream per tab: the hook lives here, above every route (specs/features/live-inbox.md).
  const live = useMailboxEvents();
  return (
    // relative: the containing block for anything absolutely positioned below (sr-only text),
    // so none of it can position against the page and stretch it past the viewport (#96).
    <div className="relative flex h-dvh flex-col overflow-hidden bg-app">
      <a
        href={`#${MAIN_CONTENT_ID}`}
        className="sr-only rounded-md bg-surface px-3 py-2 text-sm font-medium text-brand shadow focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50"
      >
        {t("app.skipToContent")}
      </a>
      <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 md:px-6">
        <div className="flex items-center gap-2">
          {/* The wordmark's "mail" is dark on light surfaces and light on dark ones. */}
          <img src={logoForLight} alt={t("app.name")} className="h-7 w-auto dark:hidden" />
          <img src={logoForDark} alt={t("app.name")} className="hidden h-7 w-auto dark:block" />
          <span className="hidden text-xs text-fg-subtle md:inline">{t("app.tagline")}</span>
        </div>
        <div className="flex items-center gap-4">
          <Link
            to="/extension"
            className="hidden text-sm font-medium text-brand hover:text-brand-strong md:inline"
          >
            {t("app.extensionPreview")}
          </Link>
          <LiveStatus state={live} />
          <AccountMenu />
        </div>
      </header>

      <DemoBanner />
      <ReconnectBanner />
      {/* Room for the phone's bottom bar (3.5rem) and the home indicator below it. */}
      <main
        className={`flex min-h-0 flex-1 md:pb-0 ${isReadingEmail ? "" : "pb-[calc(3.5rem+env(safe-area-inset-bottom))]"}`}
      >
        <SideNav />
        {/* The skip link's target: past the navigation, straight to this page's content. */}
        <div
          id={MAIN_CONTENT_ID}
          tabIndex={-1}
          className="flex min-h-0 min-w-0 flex-1 focus:outline-none"
        >
          {children}
        </div>
      </main>
      {isReadingEmail ? null : <BottomNav />}
    </div>
  );
}

/** Whether new mail arrives on its own right now; nothing is shown in the demo or signed out. */
function LiveStatus({ state }: { state: LiveState }) {
  const { t } = useTranslation();
  if (state === "off") return null;
  const isLive = state === "live";
  return (
    <span
      role="status"
      className="hidden items-center gap-1.5 text-xs text-fg-subtle md:inline-flex"
    >
      <span
        aria-hidden
        className={cn("h-2 w-2 rounded-full", isLive ? "bg-success" : "bg-warning")}
      />
      {t(isLive ? "live.on" : "live.reconnecting")}
    </span>
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
      <a href={SIGN_IN_URL} className={button({ intent: "primary", size: "sm" })}>
        {t("reconnect.signIn")}
      </a>
    </div>
  );
}

/** The signed-in account and the way out. Signing out clears every cached email from memory too. */
function AccountMenu() {
  const { t } = useTranslation();
  const session = useSession();
  const navigate = useNavigate();
  const signOut = useSignOut(() => void navigate({ to: "/signin" }));

  if (!session.data) return null;

  return (
    <div className="flex items-center gap-3 border-l border-line pl-4">
      <span
        className="hidden max-w-48 truncate text-xs text-fg-muted md:inline"
        title={session.data.email}
      >
        {session.data.email}
      </span>
      <button
        type="button"
        onClick={() => signOut.mutate()}
        disabled={signOut.isPending}
        className="min-h-11 text-sm font-medium text-fg-body hover:text-fg disabled:text-fg-subtle md:min-h-0"
      >
        {signOut.isPending ? t("account.signingOut") : t("account.signOut")}
      </button>
    </div>
  );
}
