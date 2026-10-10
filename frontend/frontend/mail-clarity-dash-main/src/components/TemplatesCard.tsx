import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import {
  useCreateTemplate,
  useDeleteTemplate,
  useTemplates,
  useTranslateTemplate,
  useUpdateTemplate,
} from "../lib/queries";
import {
  emptyTemplate,
  LANGUAGES,
  VARIABLE_WORDS,
  MAX_TEMPLATE_BODY_CHARS,
  MAX_TEMPLATE_TITLE_CHARS,
  parseTriggers,
} from "../lib/templates";
import { usePreferences } from "../lib/usePreferences";
import type { Language } from "../lib/preferences";
import type { Template, TemplateDraft } from "../types/template";
import ConfirmAction from "./ConfirmAction";
import { InlineAlert } from "./InlineMessages";
import { button, field } from "./variants";

/** The one being written: an existing template's id, or null for a new one or a translated copy. */
type Editing = { id: string | null; draft: TemplateDraft; triggers: string };

const editingOf = (id: string | null, draft: TemplateDraft): Editing => ({
  id,
  draft,
  triggers: draft.triggerKeywords?.join(", ") ?? "",
});

/** Settings > Saved replies (specs/features/reply-templates.md). Personal only. */
export default function TemplatesCard() {
  const { t } = useTranslation();
  const { preferences } = usePreferences();
  const templates = useTemplates();
  const [editing, setEditing] = useState<Editing | null>(null);

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("templates.title")}
      </h2>
      <p className="text-sm text-fg-muted">{t("templates.intro")}</p>
      {templates.isError ? (
        <InlineAlert>{errorMessage(templates.error, t, "templates.loadFailed")}</InlineAlert>
      ) : null}
      <ul className="space-y-2">
        {(templates.data ?? []).map((template) => (
          <TemplateRow
            key={template.id}
            template={template}
            onEdit={() => setEditing(editingOf(template.id, template))}
            onTranslated={(copy) => setEditing(editingOf(null, copy))}
          />
        ))}
      </ul>
      {editing ? (
        <TemplateForm editing={editing} onChange={setEditing} onDone={() => setEditing(null)} />
      ) : (
        <button
          type="button"
          onClick={() => setEditing(editingOf(null, emptyTemplate(preferences.language)))}
          className={button({ size: "sm" })}
        >
          {t("templates.new")}
        </button>
      )}
    </section>
  );
}

type TemplateRowProps = {
  template: Template;
  onEdit: () => void;
  onTranslated: (copy: TemplateDraft) => void;
};

function TemplateRow({ template, onEdit, onTranslated }: TemplateRowProps) {
  const { t } = useTranslation();
  const remove = useDeleteTemplate();
  const translate = useTranslateTemplate();
  const translateTo = async (language: Language) =>
    onTranslated(await translate.mutateAsync({ id: template.id, language }));
  return (
    <li className="space-y-2 rounded-md border border-line-subtle p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-medium text-fg">{template.title}</p>
        <p className="text-xs text-fg-subtle">{t(`templates.language.${template.language}`)}</p>
      </div>
      <p className="line-clamp-2 whitespace-pre-wrap text-xs text-fg-muted">{template.body}</p>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={onEdit} className={button({ size: "xs" })}>
          {t("templates.edit")}
        </button>
        {LANGUAGES.filter((language) => language !== template.language).map((language) => (
          <button
            key={language}
            type="button"
            disabled={translate.isPending}
            onClick={() => void translateTo(language).catch(() => undefined)}
            className={button({ size: "xs" })}
          >
            {t(`templates.translateTo.${language}`)}
          </button>
        ))}
        <ConfirmAction
          trigger={t("templates.delete")}
          triggerName={t("templates.deleteNamed", { title: template.title })}
          question={t("templates.deleteConfirm")}
          confirm={t("templates.deleteYes")}
          pending={t("templates.deleting")}
          cancel={t("templates.keep")}
          onConfirm={() => remove.mutateAsync(template.id)}
          onCancel={remove.reset}
          isPending={remove.isPending}
          error={remove.isError ? errorMessage(remove.error, t, "templates.deleteFailed") : null}
        />
      </div>
      {translate.isPending ? (
        <p className="text-xs text-fg-subtle">{t("templates.translating")}</p>
      ) : null}
      {translate.isError ? (
        <InlineAlert size="xs">
          {errorMessage(translate.error, t, "templates.translateFailed")}
        </InlineAlert>
      ) : null}
    </li>
  );
}

type TemplateFormProps = {
  editing: Editing;
  onChange: (editing: Editing) => void;
  onDone: () => void;
};

function TemplateForm({ editing, onChange, onDone }: TemplateFormProps) {
  const { t } = useTranslation();
  const hintId = useId();
  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const save = editing.id === null ? create : update;
  const setDraft = (fields: Partial<TemplateDraft>) =>
    onChange({ ...editing, draft: { ...editing.draft, ...fields } });
  const submit = async () => {
    const draft = { ...editing.draft, triggerKeywords: parseTriggers(editing.triggers) };
    if (editing.id === null) await create.mutateAsync(draft);
    else await update.mutateAsync({ id: editing.id, draft });
    onDone();
  };
  const isComplete = editing.draft.title.trim() !== "" && editing.draft.body.trim() !== "";

  return (
    <form
      className="space-y-3 rounded-md border border-line-subtle p-3"
      onSubmit={(event) => {
        event.preventDefault();
        void submit().catch(() => undefined);
      }}
    >
      <label className="block space-y-1">
        <span className="text-xs font-medium text-fg-muted">{t("templates.fieldTitle")}</span>
        <input
          value={editing.draft.title}
          maxLength={MAX_TEMPLATE_TITLE_CHARS}
          onChange={(event) => setDraft({ title: event.target.value })}
          className={`${field({ size: "sm" })} w-full`}
        />
      </label>
      <label className="block space-y-1">
        <span className="text-xs font-medium text-fg-muted">{t("templates.fieldLanguage")}</span>
        <select
          value={editing.draft.language}
          onChange={(event) =>
            setDraft({
              language:
                LANGUAGES.find((language) => language === event.target.value) ??
                editing.draft.language,
            })
          }
          className={field({ size: "sm" })}
        >
          {LANGUAGES.map((language) => (
            <option key={language} value={language}>
              {t(`templates.language.${language}`)}
            </option>
          ))}
        </select>
      </label>
      <div className="space-y-1">
        <label className="block space-y-1">
          <span className="text-xs font-medium text-fg-muted">{t("templates.fieldBody")}</span>
          <textarea
            value={editing.draft.body}
            rows={6}
            maxLength={MAX_TEMPLATE_BODY_CHARS}
            aria-describedby={`${hintId}-body`}
            onChange={(event) => setDraft({ body: event.target.value })}
            className={`${field({ size: "sm" })} w-full`}
          />
        </label>
        <VariablesHint id={`${hintId}-body`} language={editing.draft.language} />
      </div>
      <div className="space-y-1">
        <label className="block space-y-1">
          <span className="text-xs font-medium text-fg-muted">{t("templates.fieldTriggers")}</span>
          <input
            value={editing.triggers}
            aria-describedby={`${hintId}-triggers`}
            onChange={(event) => onChange({ ...editing, triggers: event.target.value })}
            className={`${field({ size: "sm" })} w-full`}
          />
        </label>
        <p id={`${hintId}-triggers`} className="text-xs text-fg-subtle">
          {t("templates.triggersHint")}
        </p>
      </div>
      {save.isError ? (
        <InlineAlert size="xs">{errorMessage(save.error, t, "templates.saveFailed")}</InlineAlert>
      ) : null}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!isComplete || save.isPending}
          className={button({ intent: "primary", size: "sm" })}
        >
          {save.isPending ? t("templates.saving") : t("templates.save")}
        </button>
        <button type="button" onClick={onDone} className={button({ size: "sm" })}>
          {t("templates.cancel")}
        </button>
      </div>
    </form>
  );
}

/** The variables AIMail fills, in the template's language; shown as code so the braces read literally. */
function VariablesHint({ id, language }: { id: string; language: Language }) {
  const { t } = useTranslation();
  const words = VARIABLE_WORDS[language];
  const rows = [
    { word: words.name, meaning: t("templates.variables.name") },
    { word: words.myName, meaning: t("templates.variables.myName") },
    { word: words.today, meaning: t("templates.variables.today") },
  ];
  return (
    <div id={id} className="space-y-1 text-xs text-fg-subtle">
      <span className="block">{t("templates.variables.intro")}</span>
      {rows.map((row) => (
        <span key={row.word} className="block">
          <code className="rounded bg-surface-muted px-1 font-mono text-fg">{`{{${row.word}}}`}</code>{" "}
          {row.meaning}
        </span>
      ))}
      <span className="block">{t("templates.variables.other")}</span>
    </div>
  );
}
