import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useFormat } from "../lib/useFormat";
import type { ThreadMessage } from "../types/email";
import MessageBody from "./MessageBody";
import WithDetails from "./WithDetails";

/** Messages of the conversation as one-line cards that expand in place, like Gmail. */
export default function ConversationMessages({ messages }: { messages: ThreadMessage[] }) {
  if (messages.length === 0) return null;
  return (
    <ol className="space-y-2">
      {messages.map((message, index) => (
        <MessageCard key={`${message.timestamp ?? ""}-${index}`} message={message} />
      ))}
    </ol>
  );
}

function MessageCard({ message }: { message: ThreadMessage }) {
  const { t } = useTranslation();
  const format = useFormat();
  const [isOpen, setIsOpen] = useState(false);
  const sender = message.isOwnReply ? t("thread.you") : message.sender;
  return (
    <li
      className={`rounded-lg border bg-surface ${message.isOwnReply ? "border-brand-line" : "border-line"}`}
    >
      <button
        type="button"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((value) => !value)}
        className="flex w-full items-baseline gap-3 px-4 py-2.5 text-left"
      >
        <span className="shrink-0 truncate text-sm font-semibold text-fg sm:max-w-[40%]">
          {sender}
        </span>
        <span
          className={`min-w-0 flex-1 text-xs text-fg-muted ${isOpen ? "invisible" : "truncate"}`}
        >
          <WithDetails text={message.snippet} />
        </span>
        {message.timestamp ? (
          <span className="shrink-0 text-xs text-fg-subtle">
            {format.timestamp(message.timestamp)}
          </span>
        ) : null}
      </button>
      {isOpen ? (
        <div className="border-t border-line-subtle px-4 py-3">
          <MessageBody body={message.body || message.snippet} />
        </div>
      ) : null}
    </li>
  );
}
