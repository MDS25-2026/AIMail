import { ImageOff, Languages } from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { restoreDetailsInHtml } from "../lib/details";
import { needsTranslation } from "../lib/detectLanguage";
import { useDetailValues } from "../lib/detailsContext";
import { useDetailsHidden } from "../lib/detailsVisibility";
import { useEmailTranslation } from "../lib/queries";
import type { Email } from "../types/email";
import { sanitizeEmailHtml } from "../lib/sanitizeEmail";
import { usePreferences } from "../lib/usePreferences";
import QuantitiesList from "./QuantitiesList";
import WithDetails from "./WithDetails";

const LOOKS_LIKE_HTML = /^\s*<[a-z!]/i;
const TAGS = /<[^>]*>/g;

/** The masked body, with an on-request translation into the reader's language. Key it by email id
 *  so a new email starts untranslated. */
export default function EmailBody({ email }: { email: Email }) {
  const { t } = useTranslation();
  const { language } = usePreferences().preferences;
  const [isShowingTranslation, setIsShowingTranslation] = useState(false);
  const translation = useEmailTranslation(email.id, language, isShowingTranslation);
  const translated = isShowingTranslation ? translation.data?.text : undefined;
  const [isAllowingImages, setIsAllowingImages] = useState(false);
  const isHtml = LOOKS_LIKE_HTML.test(email.body);
  // Offered only when it would help; kept while showing, so the original is one click away.
  const canTranslate = useMemo(
    () => needsTranslation(isHtml ? email.body.replace(TAGS, " ") : email.body, language),
    [email.body, isHtml, language],
  );
  const values = useDetailValues();
  const [isHidingDetails] = useDetailsHidden();
  const markTitle = t("details.hiddenFromAi");
  const sanitized = useMemo(() => {
    if (!isHtml) return null;
    const clean = sanitizeEmailHtml(email.body, isAllowingImages);
    // After sanitising: details go in as text, so nothing from an email can become markup.
    const html = isHidingDetails ? clean.html : restoreDetailsInHtml(clean.html, values, markTitle);
    return { ...clean, html };
  }, [email.body, isHtml, isAllowingImages, isHidingDetails, values, markTitle]);

  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 className="text-xs font-medium uppercase tracking-wide text-fg-subtle">
          {t("detail.email")}
        </h2>
        {canTranslate || isShowingTranslation ? (
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
        ) : null}
      </div>

      {isShowingTranslation && translation.isError ? (
        <p role="alert" className="mb-2 text-xs text-danger">
          {t("translate.failed")}
        </p>
      ) : null}

      {translated !== undefined ? (
        <>
          <p lang={language} className="whitespace-pre-wrap text-sm text-fg-body">
            <WithDetails text={translated} />
          </p>
          <p role="status" className="mt-2 text-[11px] text-fg-subtle">
            {t("translate.notice")}
          </p>
        </>
      ) : sanitized ? (
        <>
          {sanitized.blockedImages > 0 ? (
            <div className="mb-2 flex flex-wrap items-center gap-2 rounded-md bg-surface-muted px-3 py-2 text-xs text-fg-muted">
              <ImageOff aria-hidden className="size-3.5 shrink-0" />
              <span className="min-w-0 flex-1">{t("emailBody.imagesBlocked")}</span>
              <button
                type="button"
                onClick={() => setIsAllowingImages(true)}
                className="font-medium text-brand hover:text-brand-strong"
              >
                {t("emailBody.loadImages")}
              </button>
            </div>
          ) : null}
          <div
            // contain:paint makes this the containing block even for position:fixed, and clips to
            // it: sanitised email HTML keeps inline styles, and a fixed element must not be able to
            // draw over the dashboard (a fake button over Approve & Send).
            className="relative max-w-none overflow-x-auto text-sm text-fg-body [contain:paint] [&_a]:text-brand [&_a]:underline [&_img]:max-w-full"
            dangerouslySetInnerHTML={{ __html: sanitized.html }}
          />
        </>
      ) : (
        <p className="whitespace-pre-wrap text-sm text-fg-body">
          <WithDetails text={email.body} />
        </p>
      )}

      <QuantitiesList quantities={email.quantities ?? []} />
    </section>
  );
}
