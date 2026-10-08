import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import {
  addStyleExample,
  deleteStyleExample,
  deleteWritingStyle,
  fetchWritingStyle,
  hideStyleHabit,
  saveStyleDescription,
  setStyleLearning,
} from "../lib/api/profile";
import { MAX_DESCRIPTION_CHARS, togglePhrase, WRITING_STYLE_KEY } from "../lib/writingStyle";
import { ReplyLength, StyleHabitKind, type StyleHabit, type WritingStyle } from "../types/profile";

/**
 * Writing style (specs/features/writing-profile.md): how the reader's drafts should sound, in their
 * control. Everything shown is the masked copy the server stored, which is exactly what the AI gets.
 */

const MAX_EXAMPLE_CHARS = 1500;
const QUICK_PICKS = ["formal", "thanks", "shorter", "warmer"] as const;

const REPLY_LENGTHS: ReadonlySet<string> = new Set(Object.values(ReplyLength));
const isReplyLength = (value: string): value is ReplyLength => REPLY_LENGTHS.has(value);

const INPUT =
  "w-full rounded-md border border-line-strong bg-surface px-2 py-1 text-sm text-fg focus-visible:outline-2 focus-visible:outline-brand";
const BUTTON =
  "rounded-md bg-brand px-3 py-1.5 text-sm font-semibold text-on-brand hover:bg-brand-strong disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const QUIET_BUTTON =
  "shrink-0 rounded-md border border-line px-2 py-1 text-xs font-medium text-fg-body hover:bg-surface-muted disabled:opacity-60";

/** A failed change, in words; null while nothing has failed. */
function failureText(error: Error | null, t: TFunction): string | null {
  return error && errorMessage(error, t, "writingStyle.failed");
}

function habitText(habit: StyleHabit, t: TFunction): string {
  if (habit.kind === StyleHabitKind.Length) {
    return isReplyLength(habit.value) ? t(`writingStyle.habit.length.${habit.value}`) : "";
  }
  if (habit.kind === StyleHabitKind.Swap) {
    const [before, after] = habit.value.split(" → ");
    return t("writingStyle.habit.swap", { before, after });
  }
  return t(`writingStyle.habit.${habit.kind}`, { value: habit.value });
}

/** Every change answers with the whole stored style, so the cache is replaced, never patched. */
function useStyleChange<T>(change: (input: T) => Promise<WritingStyle | void>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (style) =>
      style
        ? queryClient.setQueryData(WRITING_STYLE_KEY, style)
        : void queryClient.invalidateQueries({ queryKey: WRITING_STYLE_KEY }),
  });
}

export default function WritingStyleCard() {
  const { t } = useTranslation();
  const style = useQuery({ queryKey: WRITING_STYLE_KEY, queryFn: fetchWritingStyle });
  return (
    <section className="space-y-5 rounded-lg border border-line bg-surface p-4">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
          {t("writingStyle.title")}
        </h2>
        <p className="mt-1 text-sm text-fg-muted">{t("writingStyle.intro")}</p>
      </div>
      {style.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t("writingStyle.loadFailed")}
        </p>
      ) : null}
      {style.data ? (
        <>
          {/* Keyed by the stored text, so deleting everything empties the box too. */}
          <Description key={style.data.description} saved={style.data.description} />
          <Examples style={style.data} />
          <Learning style={style.data} />
          <DeleteEverything />
        </>
      ) : null}
    </section>
  );
}

function AiSees({ text }: { text: string }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-md bg-surface-muted p-3 text-sm text-fg-body">
      <p className="mb-1 text-xs font-medium text-fg-subtle">{t("writingStyle.aiSees")}</p>
      <p className="whitespace-pre-wrap">{text}</p>
    </div>
  );
}

function Description({ saved }: { saved: string }) {
  const { t } = useTranslation();
  const [text, setText] = useState(saved);
  const save = useStyleChange(saveStyleDescription);
  const error = failureText(save.error, t);
  return (
    <form
      className="space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        // The box then shows what was kept, so a hidden name is visible as hidden, not as typed.
        save.mutate(text, { onSuccess: (style) => style && setText(style.description) });
      }}
    >
      <label className="block text-sm font-medium text-fg" htmlFor="style-description">
        {t("writingStyle.describe")}
      </label>
      <textarea
        id="style-description"
        rows={2}
        maxLength={MAX_DESCRIPTION_CHARS}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={t("writingStyle.describePlaceholder")}
        className={INPUT}
      />
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("writingStyle.quickLabel")}>
        {QUICK_PICKS.map((pick) => {
          const phrase = t(`writingStyle.quick.${pick}.text`);
          const isOn = text.includes(phrase);
          return (
            <button
              key={pick}
              type="button"
              aria-pressed={isOn}
              onClick={() => setText((current) => togglePhrase(current, phrase))}
              className={`rounded-full border px-3 py-1 text-xs font-medium ${
                isOn
                  ? "border-brand bg-brand-soft text-fg"
                  : "border-line text-fg-body hover:bg-surface-muted"
              }`}
            >
              {t(`writingStyle.quick.${pick}.label`)}
            </button>
          );
        })}
      </div>
      {saved ? <AiSees text={saved} /> : null}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <button type="submit" disabled={save.isPending || text === saved} className={BUTTON}>
        {save.isPending ? t("writingStyle.saving") : t("writingStyle.save")}
      </button>
    </form>
  );
}

function Examples({ style }: { style: WritingStyle }) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const add = useStyleChange((pasted: string) => addStyleExample({ text: pasted }));
  const remove = useStyleChange(deleteStyleExample);
  const isFull = style.examples.length >= style.maxExamples;
  const error = failureText(add.error ?? remove.error, t);
  return (
    <div className="space-y-2 border-t border-line-subtle pt-4">
      <p className="text-sm font-medium text-fg">
        {t("writingStyle.examples", { count: style.examples.length, max: style.maxExamples })}
      </p>
      <p className="text-xs text-fg-subtle">{t("writingStyle.examplesHint")}</p>
      <ul className="space-y-2">
        {style.examples.map((example) => (
          <li key={example.id} className="flex items-start gap-3 rounded-md bg-surface-muted p-3">
            <div className="min-w-0 flex-1">
              <p className="mb-1 text-xs font-medium text-fg-subtle">
                {t(`writingStyle.source.${example.source}`)}
              </p>
              <p className="line-clamp-4 whitespace-pre-wrap text-sm text-fg-body">
                {example.text}
              </p>
            </div>
            <button
              type="button"
              className={QUIET_BUTTON}
              disabled={remove.isPending}
              onClick={() => remove.mutate(example.id)}
            >
              {t("writingStyle.remove")}
            </button>
          </li>
        ))}
      </ul>
      {isFull ? null : (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            add.mutate(text, { onSuccess: () => setText("") });
          }}
        >
          <textarea
            rows={4}
            maxLength={MAX_EXAMPLE_CHARS}
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder={t("writingStyle.examplePlaceholder")}
            aria-label={t("writingStyle.examplePlaceholder")}
            className={INPUT}
          />
          <button type="submit" disabled={add.isPending || !text.trim()} className={BUTTON}>
            {add.isPending ? t("writingStyle.saving") : t("writingStyle.addExample")}
          </button>
        </form>
      )}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function Learning({ style }: { style: WritingStyle }) {
  const { t } = useTranslation();
  const toggle = useStyleChange(setStyleLearning);
  const hide = useStyleChange(hideStyleHabit);
  const error = failureText(toggle.error ?? hide.error, t);
  return (
    <div className="space-y-2 border-t border-line-subtle pt-4">
      <label className="flex items-center gap-2 text-sm font-medium text-fg">
        <input
          type="checkbox"
          checked={style.learning}
          disabled={toggle.isPending}
          onChange={(event) => toggle.mutate(event.target.checked)}
          className="size-4 accent-[var(--brand)]"
        />
        {t("writingStyle.learn")}
      </label>
      <p className="text-xs text-fg-subtle">{t("writingStyle.learnHint")}</p>
      {style.learning && style.habits.length === 0 ? (
        <p className="text-sm text-fg-muted">{t("writingStyle.nothingYet")}</p>
      ) : null}
      <ul className="divide-y divide-line-subtle">
        {style.habits.map((habit) => (
          <li key={habit.id} className="flex items-center justify-between gap-3 py-2 text-sm">
            <div className="min-w-0">
              <p className="text-fg-body">{habitText(habit, t)}</p>
              <p className="text-xs text-fg-muted">
                {t("writingStyle.evidence", { count: habit.evidence, outOf: habit.outOf })}
              </p>
            </div>
            <button
              type="button"
              className={QUIET_BUTTON}
              disabled={hide.isPending}
              onClick={() => hide.mutate(habit.id)}
            >
              {t("writingStyle.forget")}
            </button>
          </li>
        ))}
      </ul>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function DeleteEverything() {
  const { t } = useTranslation();
  const [isConfirming, setIsConfirming] = useState(false);
  const erase = useStyleChange(deleteWritingStyle);
  const error = failureText(erase.error, t);
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-line-subtle pt-4 text-sm">
      {isConfirming ? (
        <>
          <span className="text-fg-muted">{t("writingStyle.deleteConfirm")}</span>
          <button
            type="button"
            className="rounded-md border border-danger px-2 py-1 text-xs font-semibold text-danger"
            disabled={erase.isPending}
            onClick={() => erase.mutate(undefined, { onSuccess: () => setIsConfirming(false) })}
          >
            {t("writingStyle.deleteYes")}
          </button>
          <button type="button" className={QUIET_BUTTON} onClick={() => setIsConfirming(false)}>
            {t("writingStyle.keep")}
          </button>
        </>
      ) : (
        <button type="button" className={QUIET_BUTTON} onClick={() => setIsConfirming(true)}>
          {t("writingStyle.deleteEverything")}
        </button>
      )}
      {error ? (
        <p role="alert" className="w-full text-sm text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
