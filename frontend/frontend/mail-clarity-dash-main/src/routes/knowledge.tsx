import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import AppShell from "../components/AppShell";
import ConfirmAction from "../components/ConfirmAction";
import DocumentPreviewSheet from "../components/DocumentPreviewSheet";
import { InlineAlert, InlineStatus } from "../components/InlineMessages";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { button, field } from "../components/variants";
import { errorMessage } from "../lib/api/errors";
import { Page, pageMeta } from "../lib/pageMeta";
import { useAddDocument, useDeleteDocument, useDocuments, useUploadDocument } from "../lib/queries";
import { cn } from "../lib/utils";

type KnowledgeSearch = { doc?: string };

export const Route = createFileRoute("/knowledge")({
  validateSearch: (search: Record<string, unknown>): KnowledgeSearch => ({
    doc: typeof search.doc === "string" ? search.doc : undefined,
  }),
  head: ({ match }) => ({
    meta: [...pageMeta(match.context.preferences.language, Page.Knowledge)],
  }),
  component: KnowledgePage,
});

function KnowledgePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { doc: requestedDocId } = Route.useSearch();
  const [selectedDocId, setSelectedDocId] = useState<string | null>(requestedDocId ?? null);

  useEffect(() => {
    if (requestedDocId && requestedDocId !== selectedDocId) {
      setSelectedDocId(requestedDocId);
    }
  }, [requestedDocId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectDoc = (id: string) => {
    setSelectedDocId(id);
    void navigate({
      to: "/knowledge",
      search: { doc: id },
      replace: true,
    });
  };

  const handleClosePreview = () => {
    setSelectedDocId(null);
    void navigate({
      to: "/knowledge",
      search: { doc: undefined },
      replace: true,
    });
  };

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
                  <tr
                    key={doc.document_id}
                    onClick={() => handleSelectDoc(doc.document_id)}
                    className="group cursor-pointer border-b border-line-subtle transition-colors hover:bg-surface-muted/50 last:border-0"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-fg group-hover:text-brand">{doc.title}</span>
                        <span className="text-[10px] text-brand opacity-0 transition-opacity group-hover:opacity-100">
                          [View]
                        </span>
                      </div>
                      <div className="truncate text-xs text-fg-subtle">{doc.source}</div>
                    </td>
                    <td className="px-4 py-3 text-fg-body">{doc.doc_type}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-fg-body">
                      {doc.chunk_count}
                    </td>
                    <td
                      className="px-4 py-3 text-right"
                      onClick={(e) => e.stopPropagation()}
                    >
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

      <DocumentPreviewSheet
        documentId={selectedDocId}
        isOpen={Boolean(selectedDocId)}
        onClose={handleClosePreview}
      />
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
        className={cn(field(), "mt-3 w-full")}
      />
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        placeholder={t("knowledge.textPlaceholder")}
        aria-label={t("knowledge.textPlaceholder")}
        rows={3}
        className={cn(field(), "mt-2 w-full")}
      />
      <button
        type="button"
        disabled={!canSubmit}
        onClick={onSubmit}
        className={cn(button({ intent: "primary", size: "md" }), "mt-2")}
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
  if (error) {
    return (
      <InlineAlert size="xs" className="mt-2">
        {errorMessage(error, t, "knowledge.uploadFailed")}
      </InlineAlert>
    );
  }
  if (chunks === undefined) return null;
  return (
    <InlineStatus size="xs" className="mt-2">
      {t("knowledge.stored", { count: chunks })}
    </InlineStatus>
  );
}

/** Two steps, so a stray click never removes a policy that drafts rely on. */
function RemoveDocument({ documentId, title }: { documentId: string; title: string }) {
  const { t } = useTranslation();
  const remove = useDeleteDocument();
  return (
    <ConfirmAction
      trigger={t("knowledge.remove")}
      triggerName={t("knowledge.removeNamed", { title })}
      question={t("knowledge.removeQuestion", { title })}
      confirm={t("knowledge.removeYes")}
      pending={t("knowledge.removing")}
      cancel={t("knowledge.removeNo")}
      onConfirm={() => remove.mutateAsync(documentId)}
      onCancel={remove.reset}
      isPending={remove.isPending}
      error={remove.isError ? errorMessage(remove.error, t, "knowledge.removeFailed") : null}
    />
  );
}
