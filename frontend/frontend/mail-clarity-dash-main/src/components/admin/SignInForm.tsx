import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { AdminApiError } from "../../lib/adminApi";
import { useAdminSignIn } from "../../lib/queries";

const TOO_MANY_REQUESTS = 429;
const MESSAGE_FOR_CODE = {
  invalid_credentials: "admin.errors.invalid_credentials",
  not_an_admin: "admin.errors.not_an_admin",
  admin_auth_not_configured: "admin.errors.admin_auth_not_configured",
  supabase_unavailable: "admin.errors.supabase_unavailable",
} as const;
type ErrorKey =
  | (typeof MESSAGE_FOR_CODE)[keyof typeof MESSAGE_FOR_CODE]
  | "admin.errors.rate_limited"
  | "admin.errors.generic";

function isKnownCode(code: string): code is keyof typeof MESSAGE_FOR_CODE {
  return code in MESSAGE_FOR_CODE;
}

/** The backend's error code, as a sentence the admin can act on. */
function errorKey(error: unknown): ErrorKey {
  if (!(error instanceof AdminApiError)) return "admin.errors.generic";
  if (error.status === TOO_MANY_REQUESTS) return "admin.errors.rate_limited";
  return isKnownCode(error.code) ? MESSAGE_FOR_CODE[error.code] : "admin.errors.generic";
}

export default function SignInForm() {
  const { t } = useTranslation();
  const signIn = useAdminSignIn();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    // The password is cleared either way: it should not sit in memory after its one use.
    signIn.mutate({ email, password }, { onSettled: () => setPassword("") });
  };

  return (
    <form
      onSubmit={submit}
      className="mx-auto mt-12 w-full max-w-sm space-y-4 rounded-lg border border-line bg-surface p-6"
    >
      <div className="flex items-center gap-2">
        <ShieldCheck aria-hidden className="size-5 text-brand" />
        <h1 className="text-lg font-semibold text-fg">{t("admin.signInTitle")}</h1>
      </div>
      <p className="text-xs text-fg-muted">{t("admin.signInHint")}</p>
      <label className="block text-sm text-fg-body">
        {t("admin.email")}
        <input
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-fg"
        />
      </label>
      <label className="block text-sm text-fg-body">
        {t("admin.password")}
        <input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="mt-1 w-full rounded-md border border-line-strong bg-surface px-3 py-2 text-sm text-fg"
        />
      </label>
      {signIn.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t(errorKey(signIn.error))}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={signIn.isPending}
        className="w-full rounded-md bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong disabled:bg-surface-sunken disabled:text-fg-subtle"
      >
        {signIn.isPending ? t("admin.signingIn") : t("admin.signIn")}
      </button>
    </form>
  );
}
