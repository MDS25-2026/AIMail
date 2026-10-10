import { createFileRoute } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { Trans, useTranslation } from "react-i18next";

import AccountCard from "../components/AccountCard";
import HoldingReplyCard from "../components/HoldingReplyCard";
import PrivateModeCard from "../components/PrivateModeCard";
import ScanReadingCard from "../components/ScanReadingCard";
import TemplatesCard from "../components/TemplatesCard";
import WritingStyleCard from "../components/WritingStyleCard";
import AppShell from "../components/AppShell";
import Choice from "../components/Choice";
import { PageError, PageLoading } from "../components/PageState";
import { Page, pageMeta } from "../lib/pageMeta";
import { usePreferences } from "../lib/usePreferences";
import { Language, StatusColours, Theme, UnitSystem } from "../lib/preferences";
import { useSystemInfo } from "../lib/queries";
import { CRITIC_CONFIDENCE_THRESHOLD } from "../types/email";

export const Route = createFileRoute("/settings")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Settings) }),
  component: SettingsPage,
});

/**
 * The server values are read-only on purpose. Every one is set in the repo-root .env and read at
 * startup, so an editable form would either lie (edits lost on restart) or need a settings table
 * nothing else uses yet. The appearance card is the exception: it is this browser's own choice.
 */
function SettingsPage() {
  const { t } = useTranslation();
  const info = useSystemInfo();

  return (
    <AppShell>
      <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
        <header className="mb-5">
          <h1 className="text-xl font-semibold text-fg">{t("settings.title")}</h1>
          <p className="mt-1 text-sm text-fg-muted">
            <Trans
              i18nKey="settings.description"
              components={{ code: <code className="rounded bg-surface-sunken px-1 text-xs" /> }}
            />
          </p>
        </header>

        <div className="mb-4 grid gap-4 lg:grid-cols-2">
          <AppearanceCard />
          <AccountCard />
        </div>

        <div className="mb-4">
          <HoldingReplyCard />
        </div>

        <div className="mb-4">
          <WritingStyleCard />
        </div>

        <div className="mb-4">
          <TemplatesCard />
        </div>

        <div className="mb-4">
          <PrivateModeCard />
        </div>

        <div className="mb-4">
          <ScanReadingCard />
        </div>

        {info.isPending ? <PageLoading label={t("settings.label")} /> : null}
        {info.isError ? <PageError label={t("settings.label")} error={info.error} /> : null}

        {info.data ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Card title={t("settings.models")}>
              <Row label={t("settings.generation")} value={info.data.chat_model} />
              <Row label={t("settings.embedding")} value={info.data.embedding_model} />
              <Row label={t("settings.embeddingDim")} value={String(info.data.embedding_dim)} />
              <Row label={t("settings.classifier")} value={info.data.priority_model} />
            </Card>

            <Card title={t("knowledge.heading")}>
              <Row label={t("settings.documents")} value={String(info.data.document_count)} />
              <Row label={t("settings.chunks")} value={String(info.data.chunk_count)} />
            </Card>

            <Card title={t("settings.safety")}>
              <Row
                label={t("settings.auth")}
                value={info.data.auth_enabled ? t("settings.authOn") : t("settings.authOff")}
              />
              <Row
                label={t("settings.threshold")}
                value={t("settings.thresholdValue", { value: CRITIC_CONFIDENCE_THRESHOLD })}
              />
              <Row label={t("settings.sending")} value={t("settings.sendingValue")} />
            </Card>

            <Card title={t("settings.pregen")}>
              <Row
                label={t("settings.enabled")}
                value={info.data.auto_generate ? t("settings.yes") : t("settings.no")}
              />
              <Row
                label={t("settings.poll")}
                value={t("settings.seconds", { count: info.data.generate_poll_seconds })}
              />
            </Card>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}

function AppearanceCard() {
  const { t } = useTranslation();
  const { preferences, setTheme, setLanguage, setUnits, setColours } = usePreferences();

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("settings.appearance")}
      </h2>
      <Choice
        label={t("settings.theme")}
        value={preferences.theme}
        onChange={setTheme}
        options={[
          { value: Theme.Light, label: t("settings.themeLight") },
          { value: Theme.Dark, label: t("settings.themeDark") },
          { value: Theme.System, label: t("settings.themeSystem") },
        ]}
      />
      <Choice
        label={t("settings.language")}
        value={preferences.language}
        onChange={setLanguage}
        // Each language named in itself, so a reader can always find their own.
        options={Object.values(Language).map((language) => ({
          value: language,
          label: t(`languages.${language}`),
          lang: language,
        }))}
      />
      <Choice
        label={t("settings.units")}
        value={preferences.units}
        onChange={setUnits}
        options={[
          { value: UnitSystem.Metric, label: t("settings.metric") },
          { value: UnitSystem.Imperial, label: t("settings.imperial") },
        ]}
      />
      <Choice
        label={t("settings.colours")}
        value={preferences.colours}
        onChange={setColours}
        options={[
          { value: StatusColours.Standard, label: t("settings.coloursStandard") },
          { value: StatusColours.Friendly, label: t("settings.coloursFriendly") },
        ]}
      />
      <p className="text-xs text-fg-muted">{t("settings.coloursHint")}</p>
      <p className="pt-1 text-xs text-fg-subtle">{t("settings.preferencesNote")}</p>
    </section>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">{title}</h2>
      <dl className="mt-3 space-y-2">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-sm text-fg-muted">{label}</dt>
      <dd className="text-right text-sm font-medium text-fg">{value}</dd>
    </div>
  );
}
