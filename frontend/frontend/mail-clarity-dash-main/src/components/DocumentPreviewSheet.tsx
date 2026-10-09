import { Check, Copy, FileText, Layers, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { InlineAlert } from "./InlineMessages";
import { PageLoading } from "./PageState";
import { button } from "./variants";
import { useDocument } from "../lib/queries";
import { cn } from "../lib/utils";

export interface DocumentPreviewSheetProps {
  documentId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

type ViewMode = "reassembled" | "chunks";

export default function DocumentPreviewSheet({
  documentId,
  isOpen,
  onClose,
}: DocumentPreviewSheetProps) {
  const { t } = useTranslation();
  const { data: doc, isLoading, error } = useDocument(isOpen ? documentId : null);
  const [viewMode, setViewMode] = useState<ViewMode>("reassembled");
  const [copied, setCopied] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleCopy = async () => {
    if (!doc?.content) return;
    try {
      await navigator.clipboard.writeText(doc.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard write failed
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-rail/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <aside
        role="dialog"
        aria-label={doc?.title ? `${doc.title} preview` : "Document preview"}
        className="fixed inset-y-0 right-0 flex w-full max-w-full flex-col border-l border-line bg-surface shadow-2xl transition-transform sm:max-w-2xl"
      >
        {/* Header */}
        <header className="flex items-start justify-between border-b border-line bg-surface-elevated p-4">
          <div className="min-w-0 flex-1 pr-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-brand">
                <FileText className="h-4 w-4" />
                [POLICY DOCUMENT]
              </span>
              {doc?.doc_type ? (
                <span className="rounded-md bg-surface-muted px-2 py-0.5 text-[10px] font-medium text-fg-muted uppercase">
                  {doc.doc_type}
                </span>
              ) : null}
            </div>
            <h2 className="mt-1 truncate text-base font-semibold text-fg">
              {doc?.title || "Document Preview"}
            </h2>
            {doc?.source ? (
              <p className="mt-0.5 truncate text-xs text-fg-subtle" title={doc.source}>
                Source: {doc.source}
              </p>
            ) : null}
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close document preview"
            className="rounded-md p-1.5 text-fg-muted hover:bg-surface-muted hover:text-fg focus:outline-none focus:ring-2 focus:ring-brand"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        {/* View mode toggle & actions bar */}
        <div className="flex items-center justify-between border-b border-line bg-surface px-4 py-2 text-xs">
          <div className="flex items-center gap-1 rounded-lg border border-line bg-surface-muted p-0.5">
            <button
              type="button"
              onClick={() => setViewMode("reassembled")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition-colors",
                viewMode === "reassembled"
                  ? "bg-surface text-fg shadow-xs"
                  : "text-fg-muted hover:text-fg",
              )}
            >
              <FileText className="h-3.5 w-3.5" />
              Reassembled Full Text
            </button>
            <button
              type="button"
              onClick={() => setViewMode("chunks")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 font-medium transition-colors",
                viewMode === "chunks"
                  ? "bg-surface text-fg shadow-xs"
                  : "text-fg-muted hover:text-fg",
              )}
            >
              <Layers className="h-3.5 w-3.5" />
              Chunks ({doc?.chunk_count ?? 0})
            </button>
          </div>

          {doc?.content ? (
            <button
              type="button"
              onClick={() => void handleCopy()}
              className={cn(button({ intent: "secondary", size: "sm" }), "h-7 gap-1 text-[11px]")}
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 text-brand" />
                  [COPIED]
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  Copy Text
                </>
              )}
            </button>
          ) : null}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="py-12">
              <PageLoading label="document text" />
            </div>
          ) : null}

          {error ? (
            <InlineAlert size="sm" className="my-4">
              Unable to load document preview. The document may have been deleted or the backend is unreachable.
            </InlineAlert>
          ) : null}

          {!isLoading && !error && doc ? (
            <>
              {viewMode === "reassembled" ? (
                <div className="space-y-4">
                  <div className="rounded-lg border border-line bg-surface-muted/30 p-4">
                    <pre className="whitespace-pre-wrap font-sans text-xs leading-relaxed text-fg-body">
                      {doc.content || "Document contains no text content."}
                    </pre>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-xs text-fg-muted">
                    Displaying {doc.chunks.length} reassembled indexing chunks in sequential order:
                  </p>
                  {doc.chunks.map((chunk) => (
                    <div
                      key={chunk.id}
                      className="rounded-lg border border-line bg-surface-muted/20 p-3"
                    >
                      <div className="flex items-center justify-between border-b border-line pb-1.5 text-[11px]">
                        <span className="font-semibold text-brand">
                          Chunk #{chunk.chunk_idx + 1}
                        </span>
                        {chunk.section ? (
                          <span className="max-w-[70%] truncate font-medium text-fg-subtle">
                            Section: {chunk.section}
                          </span>
                        ) : (
                          <span className="text-[10px] text-fg-subtle">[Default Section]</span>
                        )}
                      </div>
                      <p className="mt-2 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-fg-body">
                        {chunk.content}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer info */}
        {doc ? (
          <footer className="flex items-center justify-between border-t border-line bg-surface-elevated px-4 py-2.5 text-[11px] text-fg-muted">
            <span>Reassembled {doc.chunk_count} chunks from database</span>
            <span className="font-mono text-[10px] text-fg-subtle truncate max-w-48" title={doc.document_id}>
              ID: {doc.document_id}
            </span>
          </footer>
        ) : null}
      </aside>
    </div>
  );
}
