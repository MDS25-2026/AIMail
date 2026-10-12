import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  FaqSection,
  FeaturesSection,
  LanguageSwitch,
  LanguagesSection,
  PeekSection,
  ReceiptSection,
  RedactionChip,
} from "../components/landing/LandingSections";
import LivePreview from "../components/landing/LivePreview";
import { SIGN_IN_URL } from "../lib/api/config";
import { Page, pageMeta } from "../lib/pageMeta";

// The only error codes the backend sends back here; anything else reads as a plain failure.
const SIGN_IN_ERRORS = ["sign_in_failed", "sign_in_unavailable", "sign_in_not_allowed"] as const;
type SignInError = (typeof SIGN_IN_ERRORS)[number];

function asSignInError(code: string | undefined): SignInError {
  return SIGN_IN_ERRORS.find((known) => known === code) ?? "sign_in_failed";
}

type SignInSearch = { error?: string };

export const Route = createFileRoute("/signin")({
  validateSearch: (search: Record<string, unknown>): SignInSearch => ({
    error: typeof search.error === "string" ? search.error : undefined,
  }),
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.SignIn) }),
  component: LandingPage,
});

function SignInButton({ className = "" }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <a
      href={SIGN_IN_URL}
      className={`inline-flex items-center justify-center rounded-md bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${className}`}
    >
      {t("signIn.google")}
    </a>
  );
}

/** The front door for signed-out visitors: the product working, why to trust it, one way in. */
function LandingPage() {
  const { t } = useTranslation();
  const { error } = Route.useSearch();

  return (
    <div className="min-h-dvh overflow-x-clip bg-app text-fg-body">
      <header className="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          {/* The descriptor sets this AIMail apart from other apps with a similar name. */}
          <p className="flex items-baseline gap-2">
            <span className="text-lg font-semibold tracking-tight text-fg">{t("app.name")}</span>
            <span className="text-xs text-fg-muted max-md:hidden">{t("landing.tagline")}</span>
          </p>
          <div className="flex items-center gap-3">
            <LanguageSwitch className="max-sm:hidden" />
            <SignInButton className="px-4 py-2" />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-24 px-4 pb-24 sm:px-6">
        <section className="relative isolate grid items-center gap-12 pt-8 sm:pt-20 lg:grid-cols-[1.1fr_1fr]">
          {/* A soft glow behind the hero; decorative, so it never takes focus or space. */}
          <div
            aria-hidden
            className="pointer-events-none absolute -inset-x-24 -top-10 -z-10 h-[32rem] bg-[radial-gradient(ellipse_at_30%_20%,var(--color-brand-soft),transparent_65%)]"
          />
          <div className="space-y-6">
            <LanguageSwitch className="sm:hidden" />
            {error ? (
              <p
                role="alert"
                className="rounded-md border border-danger-line bg-danger-soft p-3 text-sm text-danger"
              >
                {t(`signIn.errors.${asSignInError(error)}`)}
              </p>
            ) : null}
            <RedactionChip />
            <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-balance text-fg sm:text-5xl">
              {t("landing.headline")}
            </h1>
            <p className="max-w-xl text-lg text-fg-muted">{t("landing.lede")}</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
              <SignInButton className="px-6 py-3 text-base" />
              <span className="flex items-center gap-1.5 text-xs text-fg-muted">
                <ShieldCheck aria-hidden className="size-4 shrink-0 text-success" />
                {t("signIn.privacy")}
              </span>
            </div>
          </div>
          <LivePreview />
        </section>

        <PeekSection />
        <ReceiptSection />
        <LanguagesSection />
        <FeaturesSection />
        <FaqSection />

        <section className="rounded-2xl bg-brand px-6 py-12 text-center text-on-brand sm:px-12">
          <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {t("landing.ctaTitle")}
          </h2>
          <p className="mx-auto mt-3 max-w-xl opacity-90">{t("landing.ctaBody")}</p>
          <a
            href={SIGN_IN_URL}
            className="mt-6 inline-flex items-center justify-center rounded-md bg-surface px-6 py-3 text-base font-semibold text-brand hover:bg-surface-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-surface"
          >
            {t("signIn.google")}
          </a>
        </section>
      </main>

      <footer className="border-t border-line">
        <p className="mx-auto max-w-6xl px-4 py-6 text-xs text-fg-subtle sm:px-6">
          {t("landing.footer")}
        </p>
      </footer>
    </div>
  );
}
