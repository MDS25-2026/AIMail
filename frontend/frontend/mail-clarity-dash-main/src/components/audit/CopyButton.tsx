import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const RESET_MS = 2000;

enum CopyState {
  Idle = "idle",
  Copied = "copied",
  Failed = "failed",
}

/** Copies one value; `name` says which, for screen readers ("Copy latest hash"). */
export default function CopyButton({ value, name }: { value: string; name: string }) {
  const { t } = useTranslation();
  const [state, setState] = useState(CopyState.Idle);

  useEffect(() => {
    if (state === CopyState.Idle) return;
    const timer = setTimeout(() => setState(CopyState.Idle), RESET_MS);
    return () => clearTimeout(timer);
  }, [state]);

  const copy = () =>
    navigator.clipboard.writeText(value).then(
      () => setState(CopyState.Copied),
      () => setState(CopyState.Failed),
    );

  return (
    <span className="inline-flex items-center gap-2">
      <button
        type="button"
        onClick={() => void copy()}
        aria-label={t("audit.copyNamed", { name })}
        className="inline-flex items-center gap-1 rounded px-1 text-xs text-fg-muted hover:text-fg focus-visible:outline-2 focus-visible:outline-brand"
      >
        {state === CopyState.Copied ? (
          <Check aria-hidden className="size-3 text-success" />
        ) : (
          <Copy aria-hidden className="size-3" />
        )}
        {state === CopyState.Copied ? t("audit.copied") : t("audit.copy")}
      </button>
      {state === CopyState.Failed ? (
        <span role="alert" className="text-xs text-danger">
          {t("audit.copyFailed")}
        </span>
      ) : null}
    </span>
  );
}
