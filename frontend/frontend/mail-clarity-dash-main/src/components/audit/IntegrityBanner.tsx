import { ShieldAlert, ShieldCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { AuditTrail } from "../../types/audit";
import CopyButton from "./CopyButton";

/** Whether the whole chain holds, and the latest hash the reader should keep somewhere else. */
export default function IntegrityBanner({ trail }: { trail: AuditTrail }) {
  const { t } = useTranslation();
  const Icon = trail.isChainIntact ? ShieldCheck : ShieldAlert;
  const tone = trail.isChainIntact
    ? "border-success-line bg-success-soft"
    : "border-danger-line bg-danger-soft";
  return (
    <section className={`space-y-3 rounded-lg border p-4 ${tone}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Icon
            aria-hidden
            className={`mt-0.5 size-5 shrink-0 ${trail.isChainIntact ? "text-success" : "text-danger"}`}
          />
          <div>
            <h2 className="text-sm font-semibold text-fg">
              {trail.isChainIntact ? t("audit.chainIntact") : t("audit.chainBroken")}
            </h2>
            <p className="mt-0.5 text-xs text-fg-muted">
              {t("audit.verifiedCount", {
                verified: trail.verifiedRecords,
                total: trail.totalRecords,
              })}
            </p>
          </div>
        </div>
        <p className="text-xs text-fg-muted">
          {t("audit.algorithmLabel")}{" "}
          <span className="rounded border border-line bg-surface px-2 py-0.5 font-mono text-fg-body">
            {t("audit.algorithm")}
          </span>
        </p>
      </div>
      <HeadHash headHash={trail.headHash} />
    </section>
  );
}

function HeadHash({ headHash }: { headHash: string | null }) {
  const { t } = useTranslation();
  if (headHash === null) return <p className="text-xs text-fg-muted">{t("audit.noHeadHash")}</p>;
  return (
    <div className="space-y-1 rounded-md border border-line bg-surface p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-fg">{t("audit.headHash")}</span>
        <CopyButton value={headHash} name={t("audit.headHash")} />
      </div>
      <p className="select-all break-all font-mono text-xs text-fg-body">{headHash}</p>
      <p className="text-xs text-fg-muted">{t("audit.headHashHint")}</p>
    </div>
  );
}
