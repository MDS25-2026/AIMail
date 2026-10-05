import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { ThreadMessage } from "../types/email";
import WithDetails from "./WithDetails";

type ThreadContextToggleProps = {
  messages: ThreadMessage[];
  defaultOpen?: boolean;
};

export default function ThreadContextToggle({
  messages,
  defaultOpen = true,
}: ThreadContextToggleProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);

  if (messages.length === 0) return null;

  return (
    <section className="rounded-lg border border-line bg-surface">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
          {t("thread.title", { count: messages.length })}
        </span>
        <span aria-hidden className="text-xs text-fg-muted">
          {open ? t("thread.hide") : t("thread.show")}
        </span>
      </button>

      {open && (
        <ul className="space-y-2 border-t border-line-subtle px-4 py-3">
          {messages.map((message, index) => (
            <li key={index} className="text-xs text-fg-muted">
              <span className="font-medium text-fg-body">
                {message.isOwnReply ? t("thread.you") : message.sender}:{" "}
              </span>
              <WithDetails text={message.snippet} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
