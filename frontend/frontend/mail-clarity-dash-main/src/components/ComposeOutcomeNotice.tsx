import { TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ComposeWorkflow } from "../lib/useComposeDraft";
import { SettleOutcome } from "../types/compose";
import { button } from "./variants";

/** Gmail may have sent it: a new email has no thread to look in, so the user says what they found. */
export default function ComposeOutcomeNotice({ compose }: { compose: ComposeWorkflow }) {
  const { t } = useTranslation();
  const isBusy = compose.busy !== null;
  return (
    <div role="alert" className="rounded-md border border-warning-line bg-warning-soft p-3">
      <p className="flex items-center gap-2 text-sm font-semibold text-warning">
        <TriangleAlert aria-hidden className="size-4 shrink-0" />
        {t("compose.outcome.title")}
      </p>
      <p className="mt-1 text-sm text-fg-body">{t("compose.outcome.body")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={isBusy}
          onClick={() => compose.settle(SettleOutcome.Sent)}
          className={button({ intent: "primary", size: "sm" })}
        >
          {t("compose.outcome.wasSent")}
        </button>
        <button
          type="button"
          disabled={isBusy}
          onClick={() => compose.settle(SettleOutcome.NotSent)}
          className={button({ size: "sm" })}
        >
          {t("compose.outcome.wasNotSent")}
        </button>
      </div>
    </div>
  );
}
