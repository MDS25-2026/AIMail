import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import {
  cancelHoldingReply,
  fetchHoldingReplies,
  fetchHoldingReplySettings,
  saveHoldingReplySettings,
} from "../lib/api/settings";
import { Language } from "../lib/preferences";
import { useFormat } from "../lib/useFormat";
import {
  ActiveWhen,
  Audience,
  CancelReason,
  ReplyScope,
  type HoldingReplyRecord,
  type HoldingReplySettings,
} from "../types/settings";
import Choice from "./Choice";

/**
 * Holding reply (specs/features/holding-reply.md): the reader's own words, sent automatically
 * while they are away. Nothing here is written by AI; the preview is the exact text a sender gets.
 */

const LANGUAGES = Object.values(Language);
const WEEK = [1, 2, 3, 4, 5, 6, 7] as const;
const CANCEL_REASONS: ReadonlySet<string> = new Set(Object.values(CancelReason));
const isCancelReason = (code: string): code is CancelReason => CANCEL_REASONS.has(code);
const TIMEZONES = [
  "Asia/Kuala_Lumpur",
  "Asia/Singapore",
  "Asia/Jakarta",
  "Asia/Bangkok",
  "Asia/Hong_Kong",
  "Asia/Shanghai",
  "Asia/Tokyo",
  "Australia/Sydney",
  "Europe/London",
  "UTC",
];
const SAMPLE_NAME = "Aisyah";
const LOCALE: Record<Language, string> = {
  [Language.English]: "en-GB",
  [Language.Malay]: "ms-MY",
  [Language.Chinese]: "zh-CN",
};
const REFRESH_MS = 60_000;
const SETTINGS_KEY = ["holding-reply-settings"] as const;
const REPLIES_KEY = ["holding-replies"] as const;

const INPUT =
  "rounded-md border border-line-strong bg-surface px-2 py-1 text-sm text-fg focus-visible:outline-2 focus-visible:outline-brand";

function preview(template: string, language: Language, leaveUntil: string | null): string {
  const returnDate = leaveUntil
    ? new Intl.DateTimeFormat(LOCALE[language], { dateStyle: "long" }).format(new Date(leaveUntil))
    : "{return_date}";
  return template.replaceAll("{name}", SAMPLE_NAME).replaceAll("{return_date}", returnDate);
}

function statusText(
  reply: HoldingReplyRecord,
  t: TFunction,
  when: (iso: string) => string,
): string {
  if (reply.sentAt) return t("holdingReply.sentAt", { when: when(reply.sentAt) });
  if (reply.cancelledReason) {
    return t(
      `holdingReply.reasons.${isCancelReason(reply.cancelledReason) ? reply.cancelledReason : CancelReason.Other}`,
    );
  }
  return t("holdingReply.waitingUntil", { when: when(reply.scheduledFor) });
}

export default function HoldingReplyCard() {
  const { t } = useTranslation();
  const settings = useQuery({ queryKey: SETTINGS_KEY, queryFn: fetchHoldingReplySettings });
  return (
    <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
          {t("holdingReply.title")}
        </h2>
        <p className="mt-1 text-sm text-fg-muted">{t("holdingReply.intro")}</p>
      </div>
      {settings.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t("holdingReply.loadFailed")}
        </p>
      ) : null}
      {/* The form starts from what was saved and keeps the reader's edits from then on; a save
          writes back what the server accepted, which is what the form already shows. */}
      {settings.data ? <SettingsForm saved={settings.data} /> : null}
      <SentInYourName />
    </section>
  );
}

function SettingsForm({ saved }: { saved: HoldingReplySettings }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [form, setForm] = useState(saved);
  const [language, setLanguage] = useState<Language>(saved.defaultLanguage);
  const save = useMutation({
    mutationFn: saveHoldingReplySettings,
    onSuccess: (accepted) => queryClient.setQueryData(SETTINGS_KEY, accepted),
  });
  const update = (change: Partial<HoldingReplySettings>) =>
    setForm((current) => ({ ...current, ...change }));
  const template = form.templates[language] ?? "";
  const setTemplate = (text: string) => {
    const templates = { ...form.templates, [language]: text };
    if (!text.trim()) delete templates[language];
    update({ templates });
  };
  const error = save.error && errorMessage(save.error, t, "holdingReply.saveFailed");

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate(form);
      }}
    >
      <label className="flex items-center gap-2 text-sm font-medium text-fg">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(event) => update({ enabled: event.target.checked })}
          className="size-4 accent-[var(--brand)]"
        />
        {t("holdingReply.enabled")}
      </label>

      <Choice
        label={t("holdingReply.when")}
        value={form.activeWhen}
        onChange={(activeWhen) => update({ activeWhen })}
        options={[
          { value: ActiveWhen.OutsideHours, label: t("holdingReply.outsideHours") },
          { value: ActiveWhen.Leave, label: t("holdingReply.onLeave") },
          { value: ActiveWhen.Always, label: t("holdingReply.always") },
        ]}
      />

      {form.activeWhen === ActiveWhen.OutsideHours ? (
        <WorkingHours form={form} update={update} />
      ) : null}
      <LeaveDates form={form} update={update} />

      <Choice
        label={t("holdingReply.who")}
        value={form.audience}
        onChange={(audience) => update({ audience })}
        options={[
          { value: Audience.Correspondents, label: t("holdingReply.correspondents") },
          { value: Audience.Domain, label: t("holdingReply.domain") },
          { value: Audience.Everyone, label: t("holdingReply.everyone") },
        ]}
      />
      <Choice
        label={t("holdingReply.which")}
        value={form.scope}
        onChange={(scope) => update({ scope })}
        options={[
          { value: ReplyScope.NeedsReply, label: t("holdingReply.needsReply") },
          { value: ReplyScope.All, label: t("holdingReply.all") },
        ]}
      />
      <label className="flex items-center justify-between gap-2 text-sm text-fg-muted">
        {t("holdingReply.cooldown")}
        <input
          type="number"
          min={1}
          max={30}
          value={form.cooldownDays}
          onChange={(event) => update({ cooldownDays: Number(event.target.value) })}
          className={`${INPUT} w-20`}
        />
      </label>

      <div className="space-y-2">
        <Choice
          label={t("holdingReply.template")}
          value={language}
          onChange={setLanguage}
          options={LANGUAGES.map((code) => ({
            value: code,
            label: `${t(`languages.${code}`)}${form.templates[code] ? "" : " +"}`,
            lang: code,
          }))}
        />
        <textarea
          lang={language}
          rows={4}
          value={template}
          onChange={(event) => setTemplate(event.target.value)}
          placeholder={t("holdingReply.templatePlaceholder")}
          className={`${INPUT} w-full`}
        />
        <p className="text-xs text-fg-subtle">{t("holdingReply.fields")}</p>
        {template ? (
          <div className="rounded-md bg-surface-muted p-3 text-sm text-fg-body">
            <p className="mb-1 text-xs font-medium text-fg-subtle">{t("holdingReply.preview")}</p>
            <p lang={language} className="whitespace-pre-wrap">
              {preview(template, language, form.leaveUntil)}
            </p>
          </div>
        ) : null}
        <Choice
          label={t("holdingReply.defaultLanguage")}
          value={form.defaultLanguage}
          onChange={(defaultLanguage) => update({ defaultLanguage })}
          options={LANGUAGES.map((code) => ({
            value: code,
            label: t(`languages.${code}`),
            lang: code,
          }))}
        />
      </div>

      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      {save.isSuccess ? (
        <p role="status" className="text-sm text-success">
          {form.enabled ? t("holdingReply.savedOn") : t("holdingReply.savedOff")}
        </p>
      ) : null}
      <button
        type="submit"
        disabled={save.isPending}
        className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        {save.isPending ? t("holdingReply.saving") : t("holdingReply.save")}
      </button>
    </form>
  );
}

type SectionProps = {
  form: HoldingReplySettings;
  update: (change: Partial<HoldingReplySettings>) => void;
};

function WorkingHours({ form, update }: SectionProps) {
  const { t } = useTranslation();
  const toggleDay = (day: number) =>
    update({
      workDays: form.workDays.includes(day)
        ? form.workDays.filter((d) => d !== day)
        : [...form.workDays, day].sort(),
    });
  return (
    <fieldset className="space-y-2 rounded-md border border-line-subtle p-3">
      <legend className="px-1 text-xs font-medium text-fg-subtle">
        {t("holdingReply.workingHours")}
      </legend>
      <div className="flex flex-wrap gap-1">
        {WEEK.map((day) => (
          <label
            key={day}
            className={`cursor-pointer rounded px-2 py-1 text-xs font-medium ${
              form.workDays.includes(day)
                ? "bg-brand-soft text-fg"
                : "bg-surface-muted text-fg-muted"
            }`}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={form.workDays.includes(day)}
              onChange={() => toggleDay(day)}
            />
            {t(`holdingReply.days.${day}`)}
          </label>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
        <input
          type="time"
          value={form.workStart.slice(0, 5)}
          onChange={(event) => update({ workStart: event.target.value })}
          className={INPUT}
          aria-label={t("holdingReply.workStart")}
        />
        <span>{t("holdingReply.to")}</span>
        <input
          type="time"
          value={form.workEnd.slice(0, 5)}
          onChange={(event) => update({ workEnd: event.target.value })}
          className={INPUT}
          aria-label={t("holdingReply.workEnd")}
        />
        <select
          value={form.timezone}
          onChange={(event) => update({ timezone: event.target.value })}
          className={INPUT}
          aria-label={t("holdingReply.timezone")}
        >
          {(TIMEZONES.includes(form.timezone) ? TIMEZONES : [form.timezone, ...TIMEZONES]).map(
            (zone) => (
              <option key={zone} value={zone}>
                {zone.replace("_", " ")}
              </option>
            ),
          )}
        </select>
      </div>
    </fieldset>
  );
}

function LeaveDates({ form, update }: SectionProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-fg-muted">
      <span>{t("holdingReply.leave")}</span>
      <input
        type="date"
        value={form.leaveFrom ?? ""}
        onChange={(event) => update({ leaveFrom: event.target.value || null })}
        className={INPUT}
        aria-label={t("holdingReply.leaveFrom")}
      />
      <span>{t("holdingReply.to")}</span>
      <input
        type="date"
        value={form.leaveUntil ?? ""}
        onChange={(event) => update({ leaveUntil: event.target.value || null })}
        className={INPUT}
        aria-label={t("holdingReply.leaveUntil")}
      />
    </div>
  );
}

function SentInYourName() {
  const { t } = useTranslation();
  const replies = useQuery({
    queryKey: REPLIES_KEY,
    queryFn: fetchHoldingReplies,
    refetchInterval: REFRESH_MS,
  });
  if (!replies.data?.length) return null;
  return (
    <div className="space-y-2 border-t border-line-subtle pt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("holdingReply.sentTitle")}
      </h3>
      <ul className="divide-y divide-line-subtle">
        {replies.data.map((reply) => (
          <ReplyRow key={reply.id} reply={reply} />
        ))}
      </ul>
    </div>
  );
}

function ReplyRow({ reply }: { reply: HoldingReplyRecord }) {
  const { t } = useTranslation();
  const format = useFormat();
  const queryClient = useQueryClient();
  const cancel = useMutation({
    mutationFn: () => cancelHoldingReply(reply.id),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: REPLIES_KEY }),
  });
  const isWaiting = !reply.sentAt && !reply.cancelledReason;
  const status = statusText(reply, t, format.timestamp);
  return (
    <li className="flex items-center justify-between gap-3 py-2 text-sm">
      <div className="min-w-0">
        <p className="truncate text-fg-body">{reply.recipient}</p>
        <p className="text-xs text-fg-muted">{status}</p>
      </div>
      {isWaiting ? (
        <button
          type="button"
          onClick={() => cancel.mutate()}
          disabled={cancel.isPending}
          className="shrink-0 rounded-md border border-line px-2 py-1 text-xs font-medium text-fg-body hover:bg-surface-muted"
        >
          {t("holdingReply.cancel")}
        </button>
      ) : null}
    </li>
  );
}
