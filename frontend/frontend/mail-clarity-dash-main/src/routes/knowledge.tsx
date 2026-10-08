import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { errorMessage } from "../lib/api/errors";
import { useAddDocument, useDeleteDocument, useDocuments, useUploadDocument } from "../lib/queries";

export const Route = createFileRoute("/knowledge")({
  head: () => ({
    meta: [
      { title: "AIMail knowledge base" },
      {
        name: "description",
        content: "Policy documents AImail grounds its reply drafts in.",
      },
    ],
  }),
  component: KnowledgePage,
});

function KnowledgePage() {
  const { t } = useTranslation();
  const documents = useDocuments();
  const upload = useUploadDocument();
  const paste = useAddDocument();

  const [title, setTitle] = useState("");
  const [text, setText] = useState("");

  const handleUpload = (file: File | undefined) => {
    if (file) upload.mutate(file);
  };

  const handlePaste = () => {
    paste.mutate({ title, text }, { onSuccess: () => (setTitle(""), setText("")) });
  };

  const totalChunks = (documents.data ?? []).reduce((sum, d) => sum + d.chunk_count, 0);

  return (
    <AppShell>
      <section className="relative min-w-0 flex-1 overflow-y-auto bg-surface-muted p-6">
        <header className="mb-5">
          <h1 className="text-xl font-semibold text-fg">{t("knowledge.heading")}</h1>
          <p className="mt-1 text-sm text-fg-muted">{t("knowledge.description")}</p>
        </header>

        <div className="mb-6 grid gap-4 sm:grid-cols-2">
          <UploadCard
            onUpload={handleUpload}
            isPending={upload.isPending}
            error={upload.error}
            chunks={upload.data}
          />
          <PasteCard
            title={title}
            text={text}
            onTitle={setTitle}
            onText={setText}
            onSubmit={handlePaste}
            isPending={paste.isPending}
            error={paste.error}
            chunks={paste.data}
          />
        </div>

        {documents.isPending ? <PageLoading label={t("knowledge.label")} /> : null}
        {documents.isError ? (
          <PageError label={t("knowledge.label")} error={documents.error} />
        ) : null}
        {documents.data?.length === 0 ? (
          <PageEmpty title={t("knowledge.emptyTitle")} hint={t("knowledge.emptyHint")} />
        ) : null}

        {documents.data && documents.data.length > 0 ? (
          <div className="relative overflow-x-auto rounded-lg border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line text-xs uppercase tracking-wide text-fg-muted">
                <tr>
                  <th className="px-4 py-3 font-semibold">{t("knowledge.document")}</th>
                  <th className="px-4 py-3 font-semibold">{t("knowledge.type")}</th>
                  <th className="px-4 py-3 text-right font-semibold">{t("knowledge.chunks")}</th>
                  <th className="px-4 py-3">
                    <span className="sr-only">{t("knowledge.remove")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((doc) => (
                  <tr key={doc.document_id} className="border-b border-line-subtle last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium text-fg">{doc.title}</div>
                      <div className="truncate text-xs text-fg-subtle">{doc.source}</div>
                    </td>
                    <td className="px-4 py-3 text-fg-body">{doc.doc_type}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-fg-body">
                      {doc.chunk_count}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <RemoveDocument documentId={doc.document_id} title={doc.title} />
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-line text-fg-body">
                <tr>
                  <td className="px-4 py-3 text-xs uppercase tracking-wide" colSpan={2}>
                    {t("knowledge.documents", { count: documents.data.length })}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{totalChunks}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}

type UploadCardProps = {
  onUpload: (file: File | undefined) => void;
  isPending: boolean;
  error: unknown;
  chunks: number | undefined;
};

function UploadCard({ onUpload, isPending, error, chunks }: UploadCardProps) {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <h2 className="text-sm font-semibold text-fg">{t("knowledge.uploadTitle")}</h2>
      <p className="mt-1 text-xs text-fg-muted">{t("knowledge.uploadHint")}</p>
      <input
        type="file"
        accept="application/pdf"
        disabled={isPending}
        aria-label={t("knowledge.uploadTitle")}
        onChange={(e) => onUpload(e.target.files?.[0])}
        className="mt-3 block w-full text-sm text-fg-body file:mr-3 file:rounded-md file:border-0 file:bg-brand file:px-3 file:py-2 file:text-sm file:font-semibold file:text-on-brand hover:file:bg-brand-strong"
      />
      <ResultLine
        isPending={isPending}
        error={error}
        chunks={chunks}
        pending={t("knowledge.uploading")}
      />
    </div>
  );
}

type PasteCardProps = {
  title: string;
  text: string;
  onTitle: (value: string) => void;
  onText: (value: string) => void;
  onSubmit: () => void;
  isPending: boolean;
  error: unknown;
  chunks: number | undefined;
};

function PasteCard({
  title,
  text,
  onTitle,
  onText,
  onSubmit,
  isPending,
  error,
  chunks,
}: PasteCardProps) {
  const { t } = useTranslation();
  const canSubmit = title.trim().length > 0 && text.trim().length > 0 && !isPending;
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <h2 className="text-sm font-semibold text-fg">{t("knowledge.pasteTitle")}</h2>
      <input
        value={title}
        onChange={(e) => onTitle(e.target.value)}
        placeholder={t("knowledge.titlePlaceholder")}
        aria-label={t("knowledge.titlePlaceholder")}
        className="mt-3 w-full rounded-md border border-line-strong px-3 py-2 text-sm"
      />
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        placeholder={t("knowledge.textPlaceholder")}
        aria-label={t("knowledge.textPlaceholder")}
        rows={3}
        className="mt-2 w-full rounded-md border border-line-strong px-3 py-2 text-sm"
      />
      <button
        type="button"
        disabled={!canSubmit}
        onClick={onSubmit}
        className="mt-2 rounded-md bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-fg-subtle"
      >
        {t("knowledge.add")}
      </button>
      <ResultLine
        isPending={isPending}
        error={error}
        chunks={chunks}
        pending={t("knowledge.adding")}
      />
    </div>
  );
}

function ResultLine({
  isPending,
  error,
  chunks,
  pending,
}: {
  isPending: boolean;
  error: unknown;
  chunks: number | undefined;
  pending: string;
}) {
  const { t } = useTranslation();
  if (isPending) return <p className="mt-2 text-xs text-fg-muted">{pending}</p>;
  if (error)
    return (
      <p role="alert" className="mt-2 text-xs text-danger">
        {errorMessage(error, t, "knowledge.uploadFailed")}
      </p>
    );
  if (chunks !== undefined)
    return (
      <p role="status" className="mt-2 text-xs text-success">
        {t("knowledge.stored", { count: chunks })}
      </p>
    );
  return null;
}

/** Two steps, so a stray click never removes a policy that drafts rely on. */
function RemoveDocument({ documentId, title }: { documentId: string; title: string }) {
  const { t } = useTranslation();
  const [isConfirming, setIsConfirming] = useState(false);
  const remove = useDeleteDocument();
  if (remove.isError) {
    return (
      <span role="alert" className="text-xs text-danger">
        {t("knowledge.removeFailed")}
      </span>
    );
  }
  if (!isConfirming) {
    return (
      <button
        type="button"
        className="text-xs text-fg-muted underline hover:text-danger"
        aria-label={t("knowledge.removeNamed", { title })}
        onClick={() => setIsConfirming(true)}
      >
        {t("knowledge.remove")}
      </button>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap text-xs">
      <button
        type="button"
        className="rounded-md border border-danger px-2 py-0.5 font-semibold text-danger"
        disabled={remove.isPending}
        onClick={() => remove.mutate(documentId)}
      >
        {remove.isPending ? t("knowledge.removing") : t("knowledge.removeYes")}
      </button>
      <button
        type="button"
        className="text-fg-muted underline"
        onClick={() => setIsConfirming(false)}
      >
        {t("knowledge.removeNo")}
      </button>
    </span>
  );
}
