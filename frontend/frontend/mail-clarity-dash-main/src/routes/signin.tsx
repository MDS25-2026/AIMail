import { createFileRoute } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import { EyeOff, Inbox, Languages, PenLine, Send, ShieldCheck, UserCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SIGN_IN_URL } from "../lib/api";

// The only error codes the backend sends back here; anything else reads as a plain failure.
const SIGN_IN_ERRORS = ["sign_in_failed", "sign_in_unavailable", "sign_in_not_allowed"] as const;
type SignInError = (typeof SIGN_IN_ERRORS)[number];

function asSignInError(code: string | undefined): SignInError {
  return SIGN_IN_ERRORS.find((known) => known === code) ?? "sign_in_failed";
}

const PILLARS = [
  { icon: EyeOff, key: "private" },
  { icon: UserCheck, key: "approve" },
  { icon: Languages, key: "local" },
] as const satisfies readonly { icon: LucideIcon; key: string }[];

const STEPS = [
  { icon: Inbox, key: "arrives" },
  { icon: ShieldCheck, key: "hidden" },
  { icon: PenLine, key: "drafted" },
  { icon: Send, key: "approved" },
] as const satisfies readonly { icon: LucideIcon; key: string }[];

type SignInSearch = { error?: string };

export const Route = createFileRoute("/signin")({
  validateSearch: (search: Record<string, unknown>): SignInSearch => ({
    error: typeof search.error === "string" ? search.error : undefined,
  }),
  head: () => ({
    meta: [
      { title: "AIMail · Private email assistant" },
      {
        name: "description",
        content:
          "AIMail drafts replies to your work email, hides personal details before any AI sees them, and sends nothing without your approval.",
      },
    ],
  }),
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

/** The front door for signed-out visitors: what AIMail is, then one way in. */
function LandingPage() {
  const { t } = useTranslation();
  const { error } = Route.useSearch();

  return (
    <div className="min-h-dvh bg-app text-fg-body">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <span className="text-lg font-semibold tracking-tight text-fg">{t("app.name")}</span>
          <SignInButton className="px-4 py-2" />
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-16 px-4 py-12 sm:px-6 sm:py-16">
        <section className="max-w-2xl space-y-5">
          {error ? (
            <p
              role="alert"
              className="rounded-md border border-danger-line bg-danger-soft p-3 text-sm text-danger"
            >
              {t(`signIn.errors.${asSignInError(error)}`)}
            </p>
          ) : null}
          <h1 className="text-3xl font-semibold leading-tight text-balance text-fg sm:text-4xl">
            {t("landing.headline")}
          </h1>
          <p className="text-base text-fg-muted sm:text-lg">{t("landing.lede")}</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <SignInButton />
            <span className="flex items-center gap-1.5 text-xs text-fg-muted">
              <ShieldCheck aria-hidden className="size-4 shrink-0 text-success" />
              {t("signIn.privacy")}
            </span>
          </div>
        </section>

        <section aria-labelledby="why" className="space-y-5">
          <h2 id="why" className="text-xl font-semibold text-fg">
            {t("landing.whyTitle")}
          </h2>
          <ul className="grid gap-4 sm:grid-cols-3">
            {PILLARS.map(({ icon: Icon, key }) => (
              <li key={key} className="space-y-2 rounded-lg border border-line bg-surface p-5">
                <Icon aria-hidden className="size-5 text-brand" />
                <h3 className="text-sm font-semibold text-fg">
                  {t(`landing.pillars.${key}.title`)}
                </h3>
                <p className="text-sm text-fg-muted">{t(`landing.pillars.${key}.body`)}</p>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="how" className="space-y-5">
          <h2 id="how" className="text-xl font-semibold text-fg">
            {t("landing.howTitle")}
          </h2>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map(({ icon: Icon, key }, index) => (
              <li key={key} className="flex gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-soft text-sm font-semibold text-brand">
                  {index + 1}
                </span>
                <div className="space-y-1">
                  <p className="flex items-center gap-1.5 text-sm font-semibold text-fg">
                    <Icon aria-hidden className="size-4 text-fg-muted" />
                    {t(`landing.steps.${key}.title`)}
                  </p>
                  <p className="text-sm text-fg-muted">{t(`landing.steps.${key}.body`)}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-line">
        <p className="mx-auto max-w-5xl px-4 py-6 text-xs text-fg-subtle sm:px-6">
          {t("landing.footer")}
        </p>
      </footer>
    </div>
  );
}
