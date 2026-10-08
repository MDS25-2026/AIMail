import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import { InlineAlert } from "./InlineMessages";
import { button } from "./variants";

export type ConfirmActionProps = {
  /** The button that asks the question. */
  trigger: string;
  /** An accessible name for the trigger when its text alone is ambiguous ("Remove" which one). */
  triggerName?: string;
  question: string;
  confirm: string;
  pending: string;
  cancel: string;
  /** Resolves once the action is done; a rejection keeps the question open with `error`. */
  onConfirm: () => Promise<unknown>;
  onCancel?: () => void;
  isPending: boolean;
  /** The failure, already in words; the confirm button then reads "Try again". */
  error: string | null;
  triggerClassName?: string;
};

/**
 * A two-step action, inline: a stray click never removes or confirms anything. The safe choice
 * takes focus when the question opens, so Enter never confirms by accident, and cancelling hands
 * focus back to the trigger, so a keyboard reader does not lose their place.
 */
export default function ConfirmAction(props: ConfirmActionProps) {
  const [isOpen, setIsOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const isReturningFocus = useRef(false);

  useEffect(() => {
    if (isOpen || !isReturningFocus.current) return;
    isReturningFocus.current = false;
    triggerRef.current?.focus();
  }, [isOpen]);

  const cancel = () => {
    isReturningFocus.current = true;
    props.onCancel?.();
    setIsOpen(false);
  };
  // The rejection is already on screen through `error`; the question stays open for a retry.
  const confirm = () =>
    void props.onConfirm().then(
      () => setIsOpen(false),
      () => undefined,
    );

  if (isOpen) return <ConfirmPrompt {...props} onConfirmClick={confirm} onCancelClick={cancel} />;
  return (
    <button
      ref={triggerRef}
      type="button"
      aria-label={props.triggerName}
      onClick={() => setIsOpen(true)}
      className={cn(button({ intent: "quiet", size: "xs" }), props.triggerClassName)}
    >
      {props.trigger}
    </button>
  );
}

type PromptProps = ConfirmActionProps & { onConfirmClick: () => void; onCancelClick: () => void };

function ConfirmPrompt(props: PromptProps) {
  const { t } = useTranslation();
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => cancelRef.current?.focus(), []);
  const confirmLabel = props.error ? t("confirm.retry") : props.confirm;
  return (
    <div role="group" aria-label={props.question} className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-fg-body">{props.question}</span>
      <button
        ref={cancelRef}
        type="button"
        disabled={props.isPending}
        onClick={props.onCancelClick}
        className={button({ intent: "quiet", size: "xs" })}
      >
        {props.cancel}
      </button>
      <button
        type="button"
        disabled={props.isPending}
        onClick={props.onConfirmClick}
        className={button({ intent: "danger", size: "xs" })}
      >
        {props.isPending ? props.pending : confirmLabel}
      </button>
      {props.error ? (
        <InlineAlert size="xs" className="w-full">
          {props.error}
        </InlineAlert>
      ) : null}
    </div>
  );
}
