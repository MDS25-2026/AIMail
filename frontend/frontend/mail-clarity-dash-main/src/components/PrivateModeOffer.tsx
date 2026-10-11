import { ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { usePrivateMode, usePutOffPrivateMode, useSavePrivateMode } from "../lib/queries";
import { InlineAlert } from "./InlineMessages";
import { button } from "./variants";

/** Private mode, offered once in the inbox where the company has set it up (local-model.md, #153). */
export default function PrivateModeOffer() {
  const { t } = useTranslation();
  const mode = usePrivateMode();
  const save = useSavePrivateMode();
  const putOff = usePutOffPrivateMode();
  const offer = mode.data;
  // Only where the company set it up, and only until the user has answered either way.
  if (!offer?.available || offer.enabled || offer.isDecided) return null;
  const isSaving = save.isPending || putOff.isPending;
  const failure = save.error ?? putOff.error;
  return (
    <section
      aria-labelledby="private-offer-title"
      className="m-3 shrink-0 space-y-2 rounded-lg border border-line bg-surface-muted p-3"
    >
      <h2
        id="private-offer-title"
        className="flex items-center gap-1.5 text-sm font-semibold text-fg"
      >
        <ShieldCheck aria-hidden className="size-4 text-brand" />
        {t("privateOffer.title")}
      </h2>
      <p className="text-xs text-fg-body">{t("privateMode.intro", { model: offer.model })}</p>
      <p className="text-xs text-fg-subtle">{t("privateOffer.later")}</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={isSaving}
          onClick={() => save.mutate(true)}
          className={button({ intent: "primary", size: "sm" })}
        >
          {t("privateOffer.turnOn")}
        </button>
        <button
          type="button"
          disabled={isSaving}
          onClick={() => putOff.mutate()}
          className={button({ intent: "quiet", size: "sm" })}
        >
          {t("privateOffer.notNow")}
        </button>
      </div>
      {failure ? <InlineAlert>{errorMessage(failure, t, "privateMode.failed")}</InlineAlert> : null}
    </section>
  );
}
