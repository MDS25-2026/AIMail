import { createFileRoute } from "@tanstack/react-router";

import AppShell from "../components/AppShell";
import { PageError, PageLoading } from "../components/PageState";
import { useSystemInfo } from "../lib/queries";
import { CRITIC_CONFIDENCE_THRESHOLD } from "../types/email";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "AIMail settings" },
      { name: "description", content: "What this AImail instance is running." },
    ],
  }),
  component: SettingsPage,
});

/**
 * Read-only on purpose. Every value here is set in the repo-root .env and read at startup, so
 * an editable form would either lie (edits lost on restart) or need a settings table nothing
 * else uses yet. Showing the live configuration is honest and is what the values are for.
 */
function SettingsPage() {
  const info = useSystemInfo();

  return (
    <AppShell>
      <section className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-6">
        <header className="mb-5">
          <h1 className="text-xl font-semibold text-slate-800">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">
            What this instance is running. Values come from the server's environment; change them
            in <code className="rounded bg-slate-200 px-1 text-xs">.env</code> and restart.
          </p>
        </header>

        {info.isPending ? <PageLoading label="system information" /> : null}
        {info.isError ? <PageError label="system information" error={info.error} /> : null}

        {info.data ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Card title="Models">
              <Row label="Generation" value={info.data.chat_model} />
              <Row label="Embedding" value={info.data.embedding_model} />
              <Row label="Embedding dimensions" value={String(info.data.embedding_dim)} />
              <Row label="Priority classifier" value={info.data.priority_model} />
            </Card>

            <Card title="Knowledge base">
              <Row label="Documents" value={String(info.data.document_count)} />
              <Row label="Chunks" value={String(info.data.chunk_count)} />
            </Card>

            <Card title="Safety">
              <Row
                label="API authentication"
                value={info.data.auth_enabled ? "Required on every route" : "Not configured"}
              />
              <Row
                label="Critic confidence threshold"
                value={`${CRITIC_CONFIDENCE_THRESHOLD} — below this a draft is flagged for review`}
              />
              <Row label="Sending" value="Manual approval only; no automatic send path" />
            </Card>

            <Card title="Draft pre-generation">
              <Row label="Enabled" value={info.data.auto_generate ? "Yes" : "No"} />
              <Row label="Poll interval" value={`${info.data.generate_poll_seconds}s`} />
            </Card>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h2>
      <dl className="mt-3 space-y-2">{children}</dl>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="text-right text-sm font-medium text-slate-800">{value}</dd>
    </div>
  );
}
