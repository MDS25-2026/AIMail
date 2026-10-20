import { TriangleAlert, X } from "lucide-react";
import { useState, type ClipboardEvent, type KeyboardEvent, type Ref } from "react";
import { useTranslation } from "react-i18next";

import { maskSender } from "../lib/details";
import { useDetailsHidden } from "../lib/detailsVisibility";
import {
  acceptRecipients,
  isLikelyAddress,
  MAX_ADDRESS_CHARS,
  MAX_RECIPIENTS,
  parseRecipients,
  splitRecipients,
} from "../lib/recipients";

type RecipientsInputProps = {
  id: string;
  label: string;
  recipients: string[];
  /** Recipients in the other field: the limit counts To and Cc together. */
  otherCount: number;
  onChange: (recipients: string[]) => void;
  disabled: boolean;
  inputRef?: Ref<HTMLInputElement>;
};

/** Why typed recipients stayed in the box instead of becoming chips. */
enum Refusal {
  TooMany = "tooMany",
  TooLong = "tooLong",
}

const CHIP =
  "inline-flex max-w-full items-center gap-1 rounded-full border py-0.5 pl-2 pr-0.5 text-xs";

/**
 * To or Cc as chips. Enter, a comma, a semicolon or leaving the box makes a chip; a pasted list
 * becomes one chip per address. Anything that does not look like an address is marked, not
 * refused: the backend checks every address when the email is sent.
 */
export default function RecipientsInput({
  id,
  label,
  recipients,
  otherCount,
  onChange,
  disabled,
  inputRef,
}: RecipientsInputProps) {
  const { t } = useTranslation();
  const [isHidden] = useDetailsHidden();
  const [text, setText] = useState("");
  const [refusals, setRefusals] = useState<Refusal[]>([]);
  const shown = (recipient: string) => maskSender(recipient, isHidden);
  const unlikely = recipients.filter((recipient) => !isLikelyAddress(recipient));
  const notesId = `${id}-notes`;

  /** Adds what fits; what does not stays in the box, with the reason said, so nothing is lost. */
  const add = (more: string[], rest = "") => {
    const { accepted, tooLong, overLimit } = acceptRecipients(recipients.length + otherCount, more);
    if (accepted.length > 0) onChange([...recipients, ...accepted]);
    setRefusals([
      ...(overLimit.length > 0 ? [Refusal.TooMany] : []),
      ...(tooLong.length > 0 ? [Refusal.TooLong] : []),
    ]);
    setText([...overLimit, ...tooLong, rest].filter(Boolean).join(", "));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      add(parseRecipients(text));
      return;
    }
    if (event.key === "Backspace" && text === "" && recipients.length > 0) {
      onChange(recipients.slice(0, -1));
    }
  };

  // A pasted list is split at once, pasted where the caret is; one address stays editable.
  const handlePaste = (event: ClipboardEvent<HTMLInputElement>) => {
    const pasted = event.clipboardData.getData("text");
    if (parseRecipients(pasted).length < 2) return;
    event.preventDefault();
    const input = event.currentTarget;
    const start = input.selectionStart ?? text.length;
    const end = input.selectionEnd ?? start;
    add(parseRecipients(`${text.slice(0, start)}${pasted}${text.slice(end)}`));
  };

  const handleChange = (value: string) => {
    const { complete, rest } = splitRecipients(value);
    if (complete.length === 0) {
      setText(rest);
      return;
    }
    add(complete, rest);
  };

  return (
    <div>
      <label htmlFor={id} className="text-xs font-semibold text-fg-muted">
        {label}
      </label>
      <div className="mt-1 flex min-h-11 flex-wrap items-center gap-1.5 rounded-md border border-line-strong bg-surface px-2 py-1.5 focus-within:outline-2 focus-within:outline-brand md:min-h-0">
        {recipients.map((recipient, index) => {
          const isUnlikely = !isLikelyAddress(recipient);
          return (
            <span
              key={`${recipient}-${index}`}
              className={`${CHIP} ${
                isUnlikely
                  ? "border-warning-line bg-warning-soft text-warning"
                  : "border-line bg-surface-muted text-fg-body"
              }`}
            >
              {isUnlikely ? <TriangleAlert aria-hidden className="size-3 shrink-0" /> : null}
              <span className="truncate">{shown(recipient)}</span>
              {isUnlikely ? <span className="sr-only">{t("compose.checkAddress")}</span> : null}
              <button
                type="button"
                disabled={disabled}
                aria-label={t("compose.removeRecipient", { address: shown(recipient) })}
                onClick={() => onChange(recipients.filter((_, other) => other !== index))}
                className="inline-flex size-6 shrink-0 items-center justify-center rounded-full hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-brand disabled:cursor-not-allowed"
              >
                <X aria-hidden className="size-3" />
              </button>
            </span>
          );
        })}
        <input
          id={id}
          ref={inputRef}
          type="text"
          inputMode="email"
          autoComplete="off"
          value={text}
          disabled={disabled}
          aria-describedby={notesId}
          onChange={(event) => handleChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          onBlur={() => add(parseRecipients(text))}
          className="min-w-32 flex-1 bg-transparent py-1 text-sm text-fg outline-none placeholder:text-fg-subtle disabled:text-fg-subtle"
        />
      </div>
      {/* Always present, so a screen reader hears each warning as it appears. */}
      <div id={notesId} role="status" className="space-y-1 empty:hidden">
        {unlikely.length > 0 ? (
          <Note>{t("compose.checkAddresses", { addresses: unlikely.map(shown).join(", ") })}</Note>
        ) : null}
        {refusals.includes(Refusal.TooMany) ? (
          <Note>{t("compose.tooManyRecipients", { max: MAX_RECIPIENTS })}</Note>
        ) : null}
        {refusals.includes(Refusal.TooLong) ? (
          <Note>{t("compose.addressTooLong", { max: MAX_ADDRESS_CHARS })}</Note>
        ) : null}
      </div>
    </div>
  );
}

function Note({ children }: { children: string }) {
  return (
    <p className="mt-1 flex items-start gap-1 text-xs text-warning">
      <TriangleAlert aria-hidden className="mt-0.5 size-3 shrink-0" />
      {children}
    </p>
  );
}
