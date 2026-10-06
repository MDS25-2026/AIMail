"use client";

import { type ChangeEvent, type FormEvent, useEffect, useState } from "react";

import { ask, listDocuments, search, uploadPdf } from "@/lib/api";
import type { ContextChunk, DocumentSummary } from "@/lib/types";

export default function DashboardPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ContextChunk[]>([]);
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [answer, setAnswer] = useState<string | null>(null);
  const [asking, setAsking] = useState(false);
  const [searching, setSearching] = useState(false);
  const [status, setStatus] = useState("");

  async function refreshDocs() {
    try {
      setDocs(await listDocuments());
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to load documents");
    }
  }

  useEffect(() => {
    refreshDocs();
  }, []);

  async function onSearch(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setAnswer(null);
    setSearching(true);
    try {
      setResults(await search(query.trim()));
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function onAsk() {
    if (!query.trim()) return;
    setAsking(true);
    setAnswer("Thinking...");
    try {
      const res = await ask(query.trim());
      setAnswer(res.answer);
      setResults(res.sources);
    } catch (err) {
      setAnswer(err instanceof Error ? err.message : "Ask failed");
    } finally {
      setAsking(false);
    }
  }

  async function onUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setPreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    setStatus(`Uploading ${file.name}, embedding, storing...`);
    try {
      const chunks = await uploadPdf(file);
      setStatus(`Uploaded ${file.name} - ${chunks} chunks. Now searchable.`);
      await refreshDocs();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Upload failed");
    } finally {
      event.target.value = "";
    }
  }

  const totalChunks = docs.reduce((sum, doc) => sum + doc.chunk_count, 0);

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold">AImail dashboard</h1>
      <p className="mt-1 text-sm text-gray-500">
        Lane B - policy retrieval. Search company policy, upload PDFs to the knowledge base.
      </p>

      <form onSubmit={onSearch} className="mt-6 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Can I accept a gift from a supplier?"
          className="flex-1 rounded-lg border border-gray-300 px-4 py-3 text-sm"
        />
        <button
          type="submit"
          disabled={searching}
          className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
        >
          Search
        </button>
        <button
          type="button"
          onClick={onAsk}
          disabled={asking}
          className="rounded-lg bg-gray-900 px-5 py-3 text-sm font-semibold text-white disabled:opacity-60"
        >
          Ask
        </button>
      </form>

      {answer !== null && (
        <div className="mt-6 rounded-lg bg-gray-900 p-4 text-white">
          <div className="text-xs uppercase tracking-wide text-gray-400">Grounded answer</div>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">{answer}</p>
          <div className="mt-2 text-xs text-gray-400">Based on the passages below.</div>
        </div>
      )}

      {results.length > 0 && (
        <p className="mt-4 font-mono text-xs text-gray-400">
          embedded query (1536-d) → cosine search over {totalChunks} chunks → top {results.length}
        </p>
      )}

      <div className="mt-3 space-y-3">
        {results.map((chunk) => {
          const pct = Math.round(chunk.similarity_score * 100);
          return (
            <div key={chunk.chunk_id} className="rounded-lg border border-gray-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wide text-gray-500">
                  {chunk.source_title}
                </span>
                <span className="text-sm font-bold text-blue-600">
                  {pct}% match{" "}
                  <span className="font-mono text-xs font-normal text-gray-400">
                    cos {chunk.similarity_score.toFixed(3)}
                  </span>
                </span>
              </div>
              <div className="my-2 h-1.5 rounded bg-gray-100">
                <div className="h-full rounded bg-blue-600" style={{ width: `${pct}%` }} />
              </div>
              <p className="text-sm leading-relaxed">{chunk.content}</p>
            </div>
          );
        })}
      </div>

      <section className="mt-10 border-t border-gray-200 pt-5">
        <h2 className="text-base font-semibold">Knowledge base</h2>
        <label className="mt-3 inline-block cursor-pointer rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white">
          Upload PDF
          <input type="file" accept="application/pdf" onChange={onUpload} className="hidden" />
        </label>
        {status && <p className="mt-2 text-sm text-gray-500">{status}</p>}

        {previewUrl && (
          <iframe
            title="PDF preview"
            src={previewUrl}
            className="mt-4 h-96 w-full rounded-lg border border-gray-200"
          />
        )}

        <ul className="mt-4 divide-y divide-gray-200">
          {docs.map((doc) => (
            <li key={doc.document_id} className="flex items-baseline justify-between py-2.5">
              <div>
                <div className="text-sm font-semibold">{doc.title}</div>
                <div className="text-xs text-gray-500">{doc.source}</div>
              </div>
              <span className="text-xs font-bold text-blue-600">{doc.chunk_count} chunks</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
