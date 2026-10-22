import {
  CalendarClock,
  ExternalLink,
  FileText,
  ListTodo,
  PanelRight,
  QrCode,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { prefersReducedMotion } from "../../lib/motion";
import { Language } from "../../lib/preferences";
import { usePreferences } from "../../lib/usePreferences";
import { cn } from "../../lib/utils";
import { Filled } from "./Redacted";
import { SAMPLE } from "./sample";

const SWAP_MS = 2400;

/** The hero's badge: a real name turning into the placeholder the AI gets, over and over. */
export function RedactionChip() {
  const { t } = useTranslation();
  const [isHidden, setIsHidden] = useState(false);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const timer = window.setInterval(() => setIsHidden((hidden) => !hidden), SWAP_MS);
    return () => window.clearInterval(timer);
  }, []);
  return (
    <p className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs text-fg-muted shadow-sm">
      <span aria-hidden className="relative inline-grid font-mono">
        <span
          className={cn(
            "col-start-1 row-start-1 transition-opacity duration-500",
            isHidden && "opacity-0",
          )}
        >
          {SAMPLE.name}
        </span>
        <span
          className={cn(
            "col-start-1 row-start-1 text-brand transition-opacity duration-500",
            !isHidden && "opacity-0",
          )}
        >
          {t("landing.preview.placeholders.name")}
        </span>
      </span>
      <span className="h-3 w-px bg-line" aria-hidden />
      {t("landing.eyebrow")}
    </p>
  );
}

/** English, Bahasa Melayu and 中文 as one row of buttons, each named in itself. */
export function LanguageSwitch({ className = "" }: { className?: string }) {
  const { t } = useTranslation();
  const { preferences, setLanguage } = usePreferences();
  return (
    <div
      role="group"
      aria-label={t("landing.languageLabel")}
      className={cn("inline-flex rounded-md border border-line bg-surface p-0.5", className)}
    >
      {Object.values(Language).map((language) => (
        <button
          key={language}
          type="button"
          lang={language}
          aria-pressed={preferences.language === language}
          onClick={() => setLanguage(language)}
          className={cn(
            "rounded px-2 py-1 text-xs",
            preferences.language === language
              ? "bg-brand-soft font-semibold text-brand"
              : "text-fg-muted hover:text-fg",
          )}
        >
          {t(`languages.${language}`)}
        </button>
      ))}
    </div>
  );
}

/** One email, flipped between the reader's view and the AI's by a switch. */
export function PeekSection() {
  const { t } = useTranslation();
  const [isAiView, setIsAiView] = useState(true);
  return (
    <section aria-labelledby="peek" className="grid items-center gap-8 lg:grid-cols-2">
      <div className="space-y-4">
        <h2 id="peek" className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
          {t("landing.peek.title")}
        </h2>
        <p className="text-fg-muted">{t("landing.peek.body")}</p>
        <label className="inline-flex cursor-pointer items-center gap-3 text-sm font-medium text-fg">
          <button
            type="button"
            role="switch"
            aria-checked={isAiView}
            onClick={() => setIsAiView((value) => !value)}
            className={cn(
              "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
              isAiView ? "bg-brand" : "bg-line-strong",
            )}
          >
            <span
              className={cn(
                "size-5 rounded-full bg-surface shadow transition-transform",
                isAiView ? "translate-x-[22px]" : "translate-x-0.5",
              )}
            />
          </button>
          {t("landing.peek.toggle")}
        </label>
      </div>
      <div className="rounded-xl border border-line bg-surface p-5 shadow-sm">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-fg-subtle">
          {t(isAiView ? "landing.preview.aiView" : "landing.preview.yourView")}
        </p>
        <p className="text-xs text-fg-muted">
          <Filled template="[name] · [email]" isHidden={isAiView} />
        </p>
        <p className="mt-1 font-semibold text-fg">{t("landing.preview.subject")}</p>
        <p className="mt-2 leading-relaxed text-fg-body">
          <Filled template={t("landing.preview.body")} isHidden={isAiView} />
        </p>
      </div>
    </section>
  );
}

const RECEIPT_LINES = [
  { label: "hidden", value: "3" },
  { label: "given", value: "givenValue" },
  { label: "kept", value: "keptValue" },
  { label: "deleted", value: "deletedValue" },
  { label: "calls", value: "callsValue" },
] as const;

const RECEIPT_POINTS = ["typed", "photos", "private"] as const;

// A torn paper edge along the bottom of the receipt.
const TORN_EDGE = {
  maskImage: "radial-gradient(circle at 8px 100%, transparent 6px, #000 6.5px)",
  maskSize: "16px 100%",
  maskPosition: "0 0",
} as const;

/** The privacy receipt every email has, shown as a receipt, beside what it guarantees. */
export function ReceiptSection() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="receipt" className="grid items-center gap-10 lg:grid-cols-2">
      <div className="order-2 lg:order-1">
        <div
          className="mx-auto max-w-sm rotate-[-1.5deg] bg-surface px-6 pb-8 pt-6 font-mono text-sm shadow-lg"
          style={TORN_EDGE}
        >
          <p className="text-center text-xs font-semibold uppercase tracking-[0.2em] text-fg">
            {t("landing.receipt.heading")}
          </p>
          <p className="mt-1 text-center text-[11px] text-fg-subtle">
            {t("landing.preview.subject")}
          </p>
          <dl className="mt-4 space-y-2 border-y border-dashed border-line-strong py-4">
            {RECEIPT_LINES.map(({ label, value }) => (
              <div key={label} className="flex justify-between gap-4">
                <dt className="text-fg-muted">{t(`landing.receipt.lines.${label}`)}</dt>
                <dd className="text-right font-semibold text-fg">
                  {value === "3" ? value : t(`landing.receipt.lines.${value}`)}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-center text-[11px] text-fg-subtle">{t("app.name")}</p>
        </div>
      </div>
      <div className="order-1 space-y-4 lg:order-2">
        <h2 id="receipt" className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
          {t("landing.receipt.title")}
        </h2>
        <p className="text-fg-muted">{t("landing.receipt.body")}</p>
        <ul className="space-y-2">
          {RECEIPT_POINTS.map((point) => (
            <li key={point} className="flex gap-2 text-sm text-fg-body">
              <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-full bg-brand" />
              {t(`landing.receipt.points.${point}`)}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const SAMPLE_LANGUAGES = [Language.English, Language.Malay, Language.Chinese] as const;

/** The same reply in all three languages, the name hidden in each. */
export function LanguagesSection() {
  const { t } = useTranslation();
  return (
    <section
      aria-labelledby="languages"
      className="rounded-2xl border border-line bg-surface p-6 sm:p-10"
    >
      <div className="grid gap-8 lg:grid-cols-[1fr_1.2fr] lg:items-center">
        <div className="space-y-3">
          <h2 id="languages" className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
            {t("landing.languages.title")}
          </h2>
          <p className="text-fg-muted">{t("landing.languages.body")}</p>
        </div>
        <ul className="space-y-3">
          {SAMPLE_LANGUAGES.map((language) => (
            <li
              key={language}
              lang={language}
              className="flex items-baseline gap-3 rounded-lg bg-surface-muted px-4 py-3"
            >
              <span className="w-8 shrink-0 text-xs font-semibold uppercase text-fg-subtle">
                {language}
              </span>
              <span className="text-fg-body">
                <Filled template={t(`landing.languages.samples.${language}`)} isHidden />
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

const FEATURES = [
  { icon: FileText, key: "sources" },
  { icon: ListTodo, key: "todo" },
  { icon: CalendarClock, key: "timing" },
  { icon: WandSparkles, key: "refine" },
  { icon: Sparkles, key: "templates" },
  { icon: PanelRight, key: "panel" },
] as const satisfies readonly { icon: LucideIcon; key: string }[];

export function FeaturesSection() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="features" className="space-y-8">
      <h2
        id="features"
        className="max-w-xl text-2xl font-semibold tracking-tight text-fg sm:text-3xl"
      >
        {t("landing.featuresTitle")}
      </h2>
      <ul className="grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map(({ icon: Icon, key }) => (
          <li key={key} className="space-y-2 border-t border-line pt-4">
            <Icon aria-hidden className="size-5 text-brand" />
            <h3 className="font-semibold text-fg">{t(`landing.features.${key}.title`)}</h3>
            <p className="text-sm text-fg-muted">{t(`landing.features.${key}.body`)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

const QUESTIONS = ["send", "names", "which", "delete", "languages"] as const;

export function FaqSection() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="faq" className="mx-auto max-w-3xl space-y-6">
      <h2 id="faq" className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
        {t("landing.faqTitle")}
      </h2>
      <div className="divide-y divide-line border-y border-line">
        {QUESTIONS.map((key) => (
          <details key={key} className="group py-4">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-fg">
              {t(`landing.faq.${key}.q`)}
              <span
                aria-hidden
                className="text-xl leading-none text-fg-subtle transition-transform group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              {t(`landing.faq.${key}.a`)}
            </p>
          </details>
        ))}
      </div>
    </section>
  );
}

export const CHROME_STORE_URL =
  "https://chromewebstore.google.com/detail/aimail/jgheckckapmfmdalmeofdfekdbkiloip?pli=1";

export const FEEDBACK_FORM_URL = "https://tally.so/r/Z9jdd5";

export function ExtensionSection() {
  const { t } = useTranslation();
  return (
    <section
      aria-labelledby="extension"
      className="rounded-2xl border border-line bg-surface p-6 sm:p-10"
    >
      <div className="grid gap-8 lg:grid-cols-[1.3fr_1fr] lg:items-center">
        <div className="space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-muted px-3 py-1 text-xs font-semibold text-fg-muted">
            <PanelRight aria-hidden className="size-3.5 text-brand" />
            <span>{t("landing.extension.badge")}</span>
          </div>
          <h2 id="extension" className="text-2xl font-semibold tracking-tight text-fg sm:text-3xl">
            {t("landing.extension.title")}
          </h2>
          <p className="max-w-xl text-fg-muted leading-relaxed">{t("landing.extension.body")}</p>
          <div className="pt-2 space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <a
                href={CHROME_STORE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 rounded-md bg-brand px-5 py-2.5 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                <span>{t("landing.extension.button")}</span>
                <ExternalLink aria-hidden className="size-4" />
              </a>
              <span className="inline-flex items-center rounded-md border border-line bg-surface-muted px-2.5 py-1 text-xs font-medium text-fg-muted">
                {t("landing.extension.desktopOnlyBadge")}
              </span>
            </div>
            <p className="text-xs text-fg-subtle">{t("landing.extension.desktopNote")}</p>
          </div>
        </div>

        <div className="flex flex-col items-center justify-center rounded-xl bg-surface-muted p-6 border border-line text-center">
          <div className="rounded-xl bg-white p-3 shadow-sm border border-line">
            <img
              src="/feedback-qr.svg"
              alt={t("landing.feedback.qrAlt")}
              width={144}
              height={144}
              className="size-36 block"
            />
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-xs font-semibold text-fg">
            <QrCode aria-hidden className="size-3.5 text-brand" />
            <span>{t("landing.feedback.qrTitle")}</span>
          </div>
          <p className="mt-0.5 text-xs text-fg-muted max-w-[220px]">
            {t("landing.feedback.qrHint")}
          </p>
          <a
            href={FEEDBACK_FORM_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 text-xs font-medium text-brand underline hover:text-brand-strong"
          >
            {t("landing.feedback.link")}
          </a>
        </div>
      </div>
    </section>
  );
}
