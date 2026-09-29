import DOMPurify from "dompurify";
import { Languages } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useEmailTranslation } from "../lib/queries";
import type { Email } from "../types/email";
import { usePreferences } from "./PreferencesProvider";
import QuantitiesList from "./QuantitiesList";

const LOOKS_LIKE_HTML = /^\s*<[a-z!]/i;

/** The masked body, with an on-request translation into the reader's language. Key it by email id
 *  so a new email starts untranslated. */
export default function EmailBody({ email }: { email: Email }) {
  const { t } = useTranslation();
  const { language } = usePreferences().preferences;
  const [isShowingTranslation, setIsShowingTranslation] = useState(false);
  const translation = useEmailTranslation(email.id, language, isShowingTranslation);
  const translated = isShowingTranslation ? translation.data?.text : undefined;

  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
          {t("detail.email")}
        </h2>
        <button
          type="button"
          aria-pressed={isShowingTranslation}
          disabled={translation.isFetching}
          onClick={() => setIsShowingTranslation((value) => !value)}
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-brand hover:bg-brand-soft disabled:text-fg-subtle"
        >
          <Languages aria-hidden className="size-3.5" />
          {translation.isFetching
            ? t("translate.pending")
            : isShowingTranslation
              ? t("translate.showOriginal")
              : t("translate.action", { language: t(`languages.${language}`) })}
        </button>
      </div>

      {isShowingTranslation && translation.isError ? (
        <p role="alert" className="mb-2 text-xs text-danger">
          {t("translate.failed")}
        </p>
      ) : null}

      {translated !== undefined ? (
        <>
          <p lang={language} className="whitespace-pre-wrap text-sm text-fg-body">
            {translated}
          </p>
          <p role="status" className="mt-2 text-[11px] text-fg-subtle">
            {t("translate.notice")}
          </p>
        </>
      ) : LOOKS_LIKE_HTML.test(email.body) ? (
        <div
          className="max-w-none overflow-x-auto text-sm text-fg-body [&_a]:text-brand [&_a]:underline [&_img]:max-w-full"
          // Email HTML is untrusted — sanitize to strip scripts/handlers before rendering.
          dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(email.body) }}
        />
      ) : (
        <p className="whitespace-pre-wrap text-sm text-fg-body">{email.body}</p>
      )}

      <QuantitiesList quantities={email.quantities ?? []} />
    </section>
  );
}
