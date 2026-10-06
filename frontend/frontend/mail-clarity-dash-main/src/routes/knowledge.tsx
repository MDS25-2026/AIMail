import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import AppShell from "../components/AppShell";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { useAddDocument, useDocuments, useUploadDocument } from "../lib/queries";

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
      <section className="min-w-0 flex-1 overflow-y-auto bg-slate-50 p-6">
        <header className="mb-5">
          <h1 className="text-xl font-semibold text-slate-800">Knowledge base</h1>
          <p className="mt-1 text-sm text-slate-500">
            Policy documents AImail retrieves from when grounding a reply. Every draft cites the
            chunks it used.
          </p>
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

        {documents.isPending ? <PageLoading label="the knowledge base" /> : null}
        {documents.isError ? <PageError label="the knowledge base" error={documents.error} /> : null}
        {documents.data?.length === 0 ? (
          <PageEmpty
            title="No documents yet"
            hint="Upload a policy PDF above. Without one, drafts have nothing to ground themselves in."
          />
        ) : null}

        {documents.data && documents.data.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-semibold">Document</th>
                  <th className="px-4 py-3 font-semibold">Type</th>
                  <th className="px-4 py-3 text-right font-semibold">Chunks</th>
                </tr>
              </thead>
              <tbody>
                {documents.data.map((doc) => (
                  <tr key={doc.document_id} className="border-b border-slate-100 last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-800">{doc.title}</div>
                      <div className="truncate text-xs text-slate-400">{doc.source}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{doc.doc_type}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">
                      {doc.chunk_count}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-slate-200 text-slate-600">
                <tr>
                  <td className="px-4 py-3 text-xs uppercase tracking-wide" colSpan={2}>
                    {documents.data.length} document{documents.data.length === 1 ? "" : "s"}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold tabular-nums">{totalChunks}</td>
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
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-800">Upload a PDF</h2>
      <p className="mt-1 text-xs text-slate-500">Up to 10 MB. Must be a real PDF.</p>
      <input
        type="file"
        accept="application/pdf"
        disabled={isPending}
        onChange={(e) => onUpload(e.target.files?.[0])}
        className="mt-3 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-blue-600 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-blue-700"
      />
      <ResultLine isPending={isPending} error={error} chunks={chunks} verb="Uploading" />
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
  const canSubmit = title.trim().length > 0 && text.trim().length > 0 && !isPending;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-800">Paste policy text</h2>
      <input
        value={title}
        onChange={(e) => onTitle(e.target.value)}
        placeholder="Document title"
        className="mt-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        placeholder="Paste the policy text"
        rows={3}
        className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
      />
      <button
        type="button"
        disabled={!canSubmit}
        onClick={onSubmit}
        className="mt-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        Add document
      </button>
      <ResultLine isPending={isPending} error={error} chunks={chunks} verb="Adding" />
    </div>
  );
}

function ResultLine({
  isPending,
  error,
  chunks,
  verb,
}: {
  isPending: boolean;
  error: unknown;
  chunks: number | undefined;
  verb: string;
}) {
  if (isPending) return <p className="mt-2 text-xs text-slate-500">{verb}…</p>;
  if (error)
    return (
      <p role="alert" className="mt-2 text-xs text-red-700">
        {error instanceof Error ? error.message : "Failed"}
      </p>
    );
  if (chunks !== undefined)
    return <p className="mt-2 text-xs text-emerald-700">Stored {chunks} chunks.</p>;
  return null;
}
