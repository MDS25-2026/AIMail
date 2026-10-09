import { ImageOff, Languages } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";

import { needsTranslation } from "../lib/detectLanguage";
import { useEmailTranslation } from "../lib/queries";
import type { Email } from "../types/email";
import { looksLikeHtml, useRenderedBody } from "../lib/useRenderedBody";
import { usePreferences } from "../lib/usePreferences";
import { cn } from "../lib/utils";
import { HTML_BODY_CLASS } from "./MessageBody";
import QuantitiesList from "./QuantitiesList";
import WithDetails from "./WithDetails";

const TAGS = /<[^>]*>/g;
// About six lines of body text. Keep in step with max-h-32 on the clipped box below.
const COLLAPSED_REM = 8;

/** Whether the content is taller than the collapsed box. Re-measured as it resizes, so images that
 *  load later or a translation can turn a short body into a long one. */
function useOverflows(ref: RefObject<HTMLElement | null>) {
  const [overflows, setOverflows] = useState(false);
  useEffect(() => {
    const content = ref.current;
    if (!content) return;
    const measure = () => {
      const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
      setOverflows(content.offsetHeight > COLLAPSED_REM * rem);
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(content);
    return () => observer.disconnect();
  }, [ref]);
  return overflows;
}

/** The masked body, with an on-request translation into the reader's language. Key it by email id
 *  so a new email starts untranslated. */
export default function EmailBody({ email }: { email: Email }) {
  const { t } = useTranslation();
  const { language } = usePreferences().preferences;
  const [isShowingTranslation, setIsShowingTranslation] = useState(false);
  const translation = useEmailTranslation(email.id, language, isShowingTranslation);
  const translated = isShowingTranslation ? translation.data?.text : undefined;
  const [isAllowingImages, setIsAllowingImages] = useState(false);
  const isHtml = looksLikeHtml(email.body);
  // Offered only when it would help; kept while showing, so the original is one click away.
  const canTranslate = useMemo(
    () => needsTranslation(isHtml ? email.body.replace(TAGS, " ") : email.body, language),
    [email.body, isHtml, language],
  );
  const rendered = useRenderedBody(email.body, isAllowingImages);
  const sanitized =
    rendered.html === null ? null : { html: rendered.html, blockedImages: rendered.blockedImages };
  const [isExpanded, setIsExpanded] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const isOverflowing = useOverflows(contentRef);
  const bodyId = useId();

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

      {/* Clipped, never unmounted: collapsing keeps the translation and any loaded images. */}
      <div id={bodyId} className={cn("relative", !isExpanded && "max-h-32 overflow-hidden")}>
        <div ref={contentRef}>
          {translated !== undefined ? (
            <p lang={language} className="whitespace-pre-wrap text-sm text-fg-body">
              <WithDetails text={translated} />
            </p>
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
                className={HTML_BODY_CLASS}
                dangerouslySetInnerHTML={{ __html: sanitized.html }}
              />
            </>
          ) : (
            <p className="whitespace-pre-wrap text-sm text-fg-body">
              <WithDetails text={email.body} />
            </p>
          )}
        </div>
        {isOverflowing && !isExpanded ? (
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-12 bg-linear-to-t from-surface"
          />
        ) : null}
      </div>
      {isOverflowing ? (
        <button
          type="button"
          aria-expanded={isExpanded}
          aria-controls={bodyId}
          onClick={() => setIsExpanded((value) => !value)}
          className="mt-1 text-xs font-medium text-brand hover:text-brand-strong"
        >
          {isExpanded ? t("emailBody.showLess") : t("emailBody.showFull")}
        </button>
      ) : null}
      {/* Outside the clipped box, so a long translation never hides that it is machine-made. */}
      {translated !== undefined ? (
        <p role="status" className="mt-2 text-[11px] text-fg-subtle">
          {t("translate.notice")}
        </p>
      ) : null}

      <QuantitiesList quantities={email.quantities ?? []} />
    </section>
  );
}
