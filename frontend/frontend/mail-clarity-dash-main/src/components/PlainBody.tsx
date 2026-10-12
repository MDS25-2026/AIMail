import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { splitQuoted } from "../lib/quotedText";
import LinkedText from "./LinkedText";

/** A plain-text body: the sender's new text first, the email they quoted behind a button. */
export default function PlainBody({ text, lang }: { text: string; lang?: string }) {
  const { t } = useTranslation();
  const quotedId = useId();
  const [isShowingQuote, setIsShowingQuote] = useState(false);
  const { own, quoted } = splitQuoted(text);
  return (
    <div lang={lang} className="space-y-2 text-sm text-fg-body">
      <p className="whitespace-pre-wrap">
        <LinkedText text={own} />
      </p>
      {quoted ? (
        <>
          <button
            type="button"
            aria-expanded={isShowingQuote}
            aria-controls={quotedId}
            onClick={() => setIsShowingQuote((shown) => !shown)}
            className="min-h-11 text-xs font-medium text-brand hover:text-brand-strong md:min-h-0"
          >
            {isShowingQuote ? t("emailBody.hideQuoted") : t("emailBody.showQuoted")}
          </button>
          {isShowingQuote ? (
            <p
              id={quotedId}
              className="whitespace-pre-wrap border-l-2 border-line pl-3 text-fg-muted"
            >
              <LinkedText text={quoted} />
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
