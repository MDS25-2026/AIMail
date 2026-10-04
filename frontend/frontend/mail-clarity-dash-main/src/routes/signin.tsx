import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { SIGN_IN_URL } from "../lib/api";

// The only error codes the backend sends back here; anything else reads as a plain failure.
const SIGN_IN_ERRORS = ["sign_in_failed", "sign_in_unavailable"] as const;
type SignInError = (typeof SIGN_IN_ERRORS)[number];

function asSignInError(code: string | undefined): SignInError {
  return SIGN_IN_ERRORS.find((known) => known === code) ?? "sign_in_failed";
}

type SignInSearch = { error?: string };

export const Route = createFileRoute("/signin")({
  validateSearch: (search: Record<string, unknown>): SignInSearch => ({
    error: typeof search.error === "string" ? search.error : undefined,
  }),
  head: () => ({ meta: [{ title: "Sign in · AIMail" }] }),
  component: SignInPage,
});

function SignInPage() {
  const { t } = useTranslation();
  const { error } = Route.useSearch();
  const errorKey = asSignInError(error);

  return (
    <main className="flex min-h-dvh items-center justify-center bg-app px-4">
      <section className="w-full max-w-sm space-y-5 rounded-lg border border-line bg-surface p-6">
        <div>
          <h1 className="text-xl font-semibold text-fg">{t("app.name")}</h1>
          <p className="mt-1 text-sm text-fg-muted">{t("signIn.subtitle")}</p>
        </div>

        {error ? (
          <p
            role="alert"
            className="rounded-md border border-danger-line bg-danger-soft p-3 text-sm text-danger"
          >
            {t(`signIn.errors.${errorKey}`)}
          </p>
        ) : null}

        <a
          href={SIGN_IN_URL}
          className="flex w-full items-center justify-center rounded-md bg-brand px-4 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          {t("signIn.google")}
        </a>

        <p className="flex gap-2 text-xs text-fg-muted">
          <ShieldCheck aria-hidden className="mt-0.5 size-4 shrink-0 text-success" />
          {t("signIn.privacy")}
        </p>
      </section>
    </main>
  );
}
