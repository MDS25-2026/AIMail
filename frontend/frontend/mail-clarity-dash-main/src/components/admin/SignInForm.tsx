import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../../lib/api/errors";
import { useAdminSignIn } from "../../lib/queries";
import { cn } from "../../lib/utils";
import { InlineAlert } from "../InlineMessages";
import { button, field } from "../variants";

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
          className={cn(field(), "mt-1 w-full")}
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
          className={cn(field(), "mt-1 w-full")}
        />
      </label>
      {signIn.isError ? (
        <InlineAlert>{errorMessage(signIn.error, t, "admin.signInFailed")}</InlineAlert>
      ) : null}
      <button
        type="submit"
        disabled={signIn.isPending}
        className={cn(button({ intent: "primary", size: "md" }), "w-full")}
      >
        {signIn.isPending ? t("admin.signingIn") : t("admin.signIn")}
      </button>
    </form>
  );
}
