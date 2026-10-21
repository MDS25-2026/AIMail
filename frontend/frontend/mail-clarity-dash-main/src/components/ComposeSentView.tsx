import { CircleCheck } from "lucide-react";
import { useTranslation } from "react-i18next";

import { maskSender } from "../lib/details";
import { useDetailsHidden } from "../lib/detailsVisibility";
import { useFormat } from "../lib/useFormat";
import type { ComposeDraft } from "../types/compose";
import SourcesChips from "./SourcesChips";
import WithDetails from "./WithDetails";

/** A sent new email, read only: what went out is final. */
export default function ComposeSentView({ draft }: { draft: ComposeDraft }) {
  const { t } = useTranslation();
  const format = useFormat();
  const [isHidden] = useDetailsHidden();
  const recipients = (addresses: string[]) =>
    addresses.map((address) => maskSender(address, isHidden)).join(", ");
  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      {draft.sentAt ? (
        <p className="flex items-center gap-1.5 text-sm font-medium text-success">
          <CircleCheck aria-hidden className="size-4 shrink-0" />
          {t("compose.sentAt", { when: format.timestamp(draft.sentAt) })}
        </p>
      ) : null}
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-fg-muted">{t("compose.to")}</dt>
        <dd className="min-w-0 break-words text-fg">{recipients(draft.to)}</dd>
        {draft.cc.length > 0 ? (
          <>
            <dt className="text-fg-muted">{t("compose.cc")}</dt>
            <dd className="min-w-0 break-words text-fg">{recipients(draft.cc)}</dd>
          </>
        ) : null}
        <dt className="text-fg-muted">{t("compose.subject")}</dt>
        <dd className="min-w-0 break-words text-fg">
          <WithDetails text={draft.subject} />
        </dd>
      </dl>
      <p className="whitespace-pre-wrap text-sm leading-relaxed text-fg-body">
        <WithDetails text={draft.body} />
      </p>
      <SourcesChips sources={draft.sources ?? []} draft={draft.body} />
    </section>
  );
}
