import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { useFillTemplate, useTemplates } from "../lib/queries";
import type { DraftWorkflow } from "../lib/useDraftWorkflow";
import type { Email } from "../types/email";
import ConfirmAction from "./ConfirmAction";
import { InlineAlert } from "./InlineMessages";
import { button, field } from "./variants";

export const TEMPLATES_SECTION_ID = "saved-replies";

type TemplatePickerProps = { email: Email; workflow: DraftWorkflow };

/** Use a saved reply (specs/features/reply-templates.md), or where to make one when there are none. */
export default function TemplatePicker({ email, workflow }: TemplatePickerProps) {
  const { t } = useTranslation();
  const templates = useTemplates();
  const fill = useFillTemplate();
  const [chosenId, setChosenId] = useState("");
  const list = templates.data ?? [];
  // Hiding it until one existed left testers unable to find templates at all (test run T15).
  if (list.length === 0) {
    return (
      <p className="text-xs text-fg-muted">
        {t("templates.noneYet")}{" "}
        {/* A new tab keeps an edited draft; the list refetches on return, so the picker appears. */}
        <a
          href={`/settings#${TEMPLATES_SECTION_ID}`}
          target="_blank"
          rel="noopener"
          className="inline-flex items-center gap-1 font-medium text-brand underline"
        >
          {t("templates.addInSettings")}
          <ExternalLink aria-hidden className="size-3" />
          <span className="sr-only">{t("templates.opensInNewTab")}</span>
        </a>
      </p>
    );
  }

  const suggested = list.find((template) => template.id === email.suggestedTemplateId);
  const selected = list.find((template) => template.id === chosenId) ?? suggested ?? list[0];
  const insert = async () => {
    const { text } = await fill.mutateAsync({ templateId: selected.id, emailId: email.id });
    workflow.insertText(text);
  };
  const isDisabled = workflow.isDraftLocked || fill.isPending;

  return (
    <div className="space-y-2 rounded-md border border-line-subtle bg-surface-muted p-3">
      {suggested ? (
        <p className="text-sm text-fg">{t("templates.suggested", { title: suggested.title })}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <label className="min-w-0 flex-1">
          <span className="sr-only">{t("templates.choose")}</span>
          <select
            value={selected.id}
            onChange={(event) => setChosenId(event.target.value)}
            disabled={isDisabled}
            className={field({ size: "sm" })}
          >
            {list.map((template) => (
              <option key={template.id} value={template.id}>
                {template.id === suggested?.id
                  ? t("templates.suggestedOption", { title: template.title })
                  : template.title}
              </option>
            ))}
          </select>
        </label>
        {workflow.hasUnsavedEdits ? (
          <ConfirmAction
            trigger={t("templates.insert")}
            question={t("templates.replaceEdits")}
            confirm={t("templates.replaceYes")}
            pending={t("templates.inserting")}
            cancel={t("templates.keepEdits")}
            onConfirm={insert}
            onCancel={fill.reset}
            isPending={fill.isPending}
            error={fill.isError ? errorMessage(fill.error, t, "templates.insertFailed") : null}
          />
        ) : (
          <button
            type="button"
            disabled={isDisabled}
            onClick={() => void insert().catch(() => undefined)}
            className={button({ size: "sm" })}
          >
            {fill.isPending ? t("templates.inserting") : t("templates.insert")}
          </button>
        )}
        <button
          type="button"
          disabled={isDisabled}
          onClick={() => void workflow.draftFromTemplate(selected.id).catch(() => undefined)}
          className={button({ size: "sm" })}
        >
          {workflow.isTemplating ? t("templates.drafting") : t("templates.adapt")}
        </button>
      </div>
      {fill.isError && !workflow.hasUnsavedEdits ? (
        <InlineAlert size="xs">{errorMessage(fill.error, t, "templates.insertFailed")}</InlineAlert>
      ) : null}
    </div>
  );
}
