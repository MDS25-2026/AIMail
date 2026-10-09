import { useNavigate } from "@tanstack/react-router";
import {
  ChevronDown,
  ChevronUp,
  FileText,
  Mail,
  MessageSquare,
  RotateCcw,
  Send,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  searchInbox,
  type ChatMessage,
  type SearchSource,
} from "../lib/api/search";
import { useSession } from "../lib/queries";
import { cn } from "../lib/utils";
import FormattedChatMessage from "./FormattedChatMessage";

export default function InboxChatWidget() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const session = useSession();
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [expandedSources, setExpandedSources] = useState<Record<number, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      inputRef.current?.focus();
    }
  }, [isOpen, messages, isLoading]);

  const handleResetChat = () => {
    setMessages([]);
    setExpandedSources({});
    setInput("");
  };

  const toggleSourceExpand = (messageIndex: number) => {
    setExpandedSources((prev) => ({
      ...prev,
      [messageIndex]: !prev[messageIndex],
    }));
  };

  const handleSourceClick = (source: SearchSource) => {
    if (source.source_type === "email") {
      void navigate({
        to: "/",
        search: { email: source.id },
      });
    } else {
      void navigate({
        to: "/knowledge",
        search: { doc: source.id },
      });
    }
  };

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText ?? input).trim();
    if (!textToSend || isLoading) return;

    const userMessage: ChatMessage = { role: "user", content: textToSend };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setIsLoading(true);

    try {
      // Pass recent history to resolve multi-turn conversational context
      const historyForApi = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await searchInbox({
        query: textToSend,
        history: historyForApi,
        k_emails: 5,
        k_docs: 3,
      });

      // Restore zero-knowledge sender tokens locally from client-side vault
      let restoredAnswer = response.answer;
      if (response.sender_vault) {
        for (const [placeholder, realSender] of Object.entries(response.sender_vault)) {
          restoredAnswer = restoredAnswer.replaceAll(placeholder, realSender);
        }
      }

      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: restoredAnswer,
        sources: response.sources,
      };

      setMessages([...updatedMessages, assistantMessage]);
    } catch {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content:
          "Unable to complete the search query. Please verify that the backend services are running and try again.",
      };
      setMessages([...updatedMessages, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  };

  const samplePrompts = [
    "What discounts did we discuss with clients?",
    "When is the next scheduled deployment deadline?",
    "What is our standard SLA policy?",
  ];

  if (!session.data) return null;

  return (
    <>
      {/* Floating Trigger Button: Bottom-Left Anchor */}
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-label={isOpen ? "Close inbox assistant" : "Open inbox assistant"}
        className={cn(
          "fixed bottom-4 left-4 z-50 flex h-11 w-11 items-center justify-center rounded-full shadow-lg transition-transform hover:scale-105 active:scale-95 focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2",
          isOpen
            ? "bg-surface-elevated text-fg border border-line"
            : "bg-brand text-brand-fg",
        )}
      >
        {isOpen ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

      {/* Floating Chat Card: Bottom-Left Anchor (Responsive Mobile Drawer on small viewports) */}
      {isOpen && (
        <div
          role="dialog"
          aria-label="Inbox Assistant Chat"
          className="fixed inset-x-2 bottom-16 top-16 z-50 flex flex-col overflow-hidden rounded-xl border border-line bg-surface shadow-2xl sm:inset-auto sm:bottom-16 sm:left-4 sm:h-[540px] sm:w-[380px]"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-line bg-surface-elevated px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10 text-brand">
                <Sparkles className="h-4 w-4" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-fg">Inbox Assistant</h3>
                <span className="text-[10px] text-fg-muted uppercase tracking-wider">
                  [Grounded Q&A]
                </span>
              </div>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={handleResetChat}
                title="New conversation"
                aria-label="New conversation"
                className="rounded-md p-1.5 text-fg-muted hover:bg-surface-muted hover:text-fg"
              >
                <RotateCcw className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Minimize chat"
                aria-label="Minimize chat"
                className="rounded-md p-1.5 text-fg-muted hover:bg-surface-muted hover:text-fg"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Conversation Body */}
          <div className="flex-1 space-y-4 overflow-y-auto p-4 text-xs">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col justify-center space-y-3 py-6 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-surface-muted text-brand">
                  <Sparkles className="h-5 w-5" />
                </div>
                <h4 className="text-sm font-medium text-fg">Ask your inbox</h4>
                <p className="px-4 text-xs text-fg-muted">
                  Ask natural language questions about your email correspondence and company policies.
                </p>

                <div className="mt-2 flex flex-col gap-1.5 px-2 text-left">
                  {samplePrompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => void handleSend(prompt)}
                      className="rounded-md border border-line bg-surface-muted px-2.5 py-1.5 text-left text-[11px] text-fg hover:border-brand/40 hover:bg-surface"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={cn("flex flex-col", msg.role === "user" ? "items-end" : "items-start")}
              >
                <div
                  className={cn(
                    "max-w-[88%] rounded-lg px-3 py-2 text-xs leading-relaxed",
                    msg.role === "user"
                      ? "bg-brand text-brand-fg font-medium"
                      : "bg-surface-elevated text-fg border border-line shadow-xs",
                  )}
                >
                  {msg.role === "assistant" ? (
                    <FormattedChatMessage content={msg.content} />
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>

                {/* Sources Chip & Expandable Cards */}
                {msg.role === "assistant" && msg.sources && msg.sources.length > 0 ? (
                  <div className="mt-1.5 max-w-[95%]">
                    <button
                      type="button"
                      onClick={() => toggleSourceExpand(idx)}
                      className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-muted px-2.5 py-1 text-[11px] font-medium text-fg hover:border-brand/50"
                    >
                      <span className="text-brand font-semibold">{msg.sources.length} sources</span>
                      <span className="text-fg-muted">
                        ({msg.sources.filter((s) => s.source_type === "email").length} emails,{" "}
                        {msg.sources.filter((s) => s.source_type === "document").length} docs)
                      </span>
                      {expandedSources[idx] ? (
                        <ChevronUp className="h-3 w-3 text-fg-muted" />
                      ) : (
                        <ChevronDown className="h-3 w-3 text-fg-muted" />
                      )}
                    </button>

                    {expandedSources[idx] && (
                      <div className="mt-2 space-y-1.5">
                        {msg.sources.map((source, sIdx) => (
                          <div
                            key={sIdx}
                            onClick={() => handleSourceClick(source)}
                            className="group flex cursor-pointer flex-col rounded-md border border-line bg-surface p-2 transition-colors hover:border-brand/60 hover:bg-surface-elevated"
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-brand">
                                {source.source_type === "email" ? (
                                  <>
                                    <Mail className="h-3 w-3" />
                                    [Email]
                                  </>
                                ) : (
                                  <>
                                    <FileText className="h-3 w-3" />
                                    [Policy Document]
                                  </>
                                )}
                              </span>
                              <span className="text-[10px] text-fg-muted">
                                {source.source_type === "email" ? "Click to view email" : "Click to preview document"}
                              </span>
                            </div>
                            <span className="mt-0.5 line-clamp-1 font-medium text-fg group-hover:text-brand">
                              {source.title}
                            </span>
                            <span className="text-[10px] text-fg-muted">{source.subtitle}</span>
                            <p className="mt-1 line-clamp-2 text-[10px] text-fg-subtle">
                              {source.snippet}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            ))}

            {isLoading && (
              <div className="flex items-center gap-2 text-fg-muted">
                <div className="h-2 w-2 animate-ping rounded-full bg-brand" />
                <span className="text-xs">Searching inbox & synthesizing answer...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Footer Input Bar */}
          <div className="border-t border-line bg-surface-elevated p-2.5">
            <div className="flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1.5 focus-within:border-brand focus-within:ring-1 focus-within:ring-brand">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about your emails..."
                disabled={isLoading}
                className="min-w-0 flex-1 bg-transparent text-xs text-fg placeholder:text-fg-subtle focus:outline-none disabled:opacity-50"
              />
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!input.trim() || isLoading}
                aria-label="Send query"
                className="flex h-7 w-7 items-center justify-center rounded-md bg-brand text-brand-fg transition-opacity hover:opacity-90 disabled:opacity-30"
              >
                <Send className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
