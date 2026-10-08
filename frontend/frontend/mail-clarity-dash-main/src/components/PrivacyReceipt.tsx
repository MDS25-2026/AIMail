import { ReceiptText } from "lucide-react";
import { useTranslation } from "react-i18next";

import { detailValues } from "../lib/details";
import { useDetailsHidden } from "../lib/detailsVisibility";
import { hiddenCounts } from "../lib/hiddenDetails";
import { kindOf } from "../lib/masking";
import type { Email } from "../types/email";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";

/** What left for the AI and what stayed with the reader, for one email (#158). */
export default function PrivacyReceipt({ email }: { email: Email }) {
  const { t } = useTranslation();
  const [isHidden] = useDetailsHidden();
  const counts = hiddenCounts(`${email.subject}\n${email.body}`);
  const kept = [...detailValues(email.details)];
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-xs font-medium text-fg-muted hover:bg-surface-muted hover:text-fg-body"
        >
          <ReceiptText aria-hidden className="size-4" />
          {t("receipt.open")}
        </button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <div className="relative max-h-[80vh] space-y-4 overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{t("receipt.title")}</DialogTitle>
            <DialogDescription>{t("receipt.description")}</DialogDescription>
          </DialogHeader>

          <section>
            <h3 className="text-sm font-semibold text-fg">{t("receipt.hiddenTitle")}</h3>
            {counts.length === 0 ? (
              <p className="mt-1 text-sm text-fg-muted">{t("receipt.noneHidden")}</p>
            ) : (
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {counts.map(({ kind, count }) => (
                  <li
                    key={kind}
                    className="rounded-full bg-brand-soft px-2 py-0.5 text-xs text-brand"
                  >
                    {t("receipt.count", { count, kind: t(`hiddenDetails.kind.${kind}`) })}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <div className="grid gap-4 md:grid-cols-2">
            <section>
              <h3 className="text-sm font-semibold text-fg">{t("receipt.sentTitle")}</h3>
              <p className="text-xs text-fg-muted">{t("receipt.sentHint")}</p>
              <pre className="relative mt-2 max-h-80 overflow-y-auto whitespace-pre-wrap rounded-md border border-line bg-surface-muted p-3 font-mono text-xs text-fg-body">
                {email.body}
              </pre>
            </section>
            <section>
              <h3 className="text-sm font-semibold text-fg">{t("receipt.keptTitle")}</h3>
              <p className="text-xs text-fg-muted">{t("receipt.keptHint")}</p>
              {kept.length === 0 ? (
                <p className="mt-2 text-sm text-fg-muted">{t("receipt.noneKept")}</p>
              ) : (
                <dl className="mt-2 space-y-1 text-sm">
                  {kept.map(([placeholder, value]) => (
                    <div key={placeholder} className="flex gap-2">
                      <dt className="font-mono text-xs text-fg-muted">{placeholder}</dt>
                      <dd className="text-fg">
                        {isHidden ? t(`hiddenDetails.kind.${kindOf(placeholder)}`) : value}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          </div>
          <p className="text-xs text-fg-muted">{t("receipt.alsoSent")}</p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
