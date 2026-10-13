import { Languages } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { mainLanguage, needsTranslation } from "../lib/detectLanguage";
import { useTranslateDraft } from "../lib/queries";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import type { Email } from "../types/email";
import { InlineAlert } from "./InlineMessages";
import { button } from "./variants";

/** Write the reply in your own language, send it in theirs (specs/features/write-in-my-language.md).
 *  Offered only when the draft is not in the email's language; the translation then goes through the
 *  same checks as any draft before it can be sent. */
export default function TranslateDraft({
  email,
  workflow,
}: {
  email: Email;
  workflow: DraftWorkflow;
}) {
  const { t } = useTranslation();
  const translate = useTranslateDraft();
  // Your words before the translation, to compare with it and to go back to.
  const [original, setOriginal] = useState<string | null>(null);
  const target = mainLanguage(email.body);
  const isOffered =
    target !== null && workflow.draft.trim() !== "" && needsTranslation(workflow.draft, target);

  if (original !== null) {
    return (
      <div className="space-y-2 rounded-md border border-line bg-surface-muted p-3 text-xs">
        <p className="font-semibold text-fg-muted">{t("writeInMine.yourWords")}</p>
        <p className="whitespace-pre-wrap text-fg-body">{original}</p>
        <p className="text-fg-subtle">{t("writeInMine.check")}</p>
        <button
          type="button"
          onClick={() => {
            workflow.setDraft(original);
            setOriginal(null);
          }}
          className={button({ size: "xs" })}
        >
          {t("writeInMine.undo")}
        </button>
      </div>
    );
  }
  if (!isOffered || workflow.isDraftLocked) return null;
  return (
    <div className="space-y-1">
      <button
        type="button"
        disabled={translate.isPending}
        onClick={() => {
          const typed = workflow.draft;
          translate.mutate(
            { emailId: email.id, text: typed },
            {
              onSuccess: ({ text }) => {
                setOriginal(typed);
                workflow.insertText(text);
              },
            },
          );
        }}
        className={button({ size: "sm" })}
      >
        <Languages aria-hidden className="size-4" />
        {translate.isPending
          ? t("translate.pending")
          : t("writeInMine.translateTo", { language: t(`languages.${target}`) })}
      </button>
      {translate.isError ? (
        <InlineAlert size="xs">
          {errorMessage(translate.error, t, "writeInMine.failed")}
        </InlineAlert>
      ) : null}
    </div>
  );
}
