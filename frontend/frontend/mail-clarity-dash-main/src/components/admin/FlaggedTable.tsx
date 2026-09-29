import { useTranslation } from "react-i18next";

import { useFormat } from "../../lib/useFormat";
import type { FlaggedDraft } from "../../types/admin";

/** Subjects here are the stored, masked ones; reasons are categories with any quoted text cut. */
export default function FlaggedTable({ drafts }: { drafts: FlaggedDraft[] }) {
  const { t } = useTranslation();
  const format = useFormat();
  if (drafts.length === 0) return <p className="text-sm text-fg-subtle">{t("admin.noData")}</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-line text-xs uppercase tracking-wide text-fg-muted">
          <tr>
            <th className="py-2 pr-4 font-semibold">{t("admin.subject")}</th>
            <th className="py-2 pr-4 font-semibold">{t("admin.reasons")}</th>
            <th className="py-2 pr-4 text-right font-semibold">{t("admin.confidence")}</th>
            <th className="py-2 font-semibold">{t("admin.generatedAt")}</th>
          </tr>
        </thead>
        <tbody>
          {drafts.map((draft) => (
            <tr key={draft.id} className="border-b border-line-subtle align-top last:border-0">
              <td className="max-w-xs truncate py-2 pr-4 text-fg">
                {draft.subject || <span className="text-fg-subtle">{t("admin.noSubject")}</span>}
              </td>
              <td className="py-2 pr-4">
                <ul className="flex flex-wrap gap-1">
                  {draft.reasons.map((reason) => (
                    <li
                      key={reason}
                      className="rounded bg-surface-sunken px-1.5 py-0.5 text-xs text-fg-body"
                    >
                      {reason}
                    </li>
                  ))}
                </ul>
              </td>
              <td className="py-2 pr-4 text-right tabular-nums text-fg-body">
                {draft.confidence === null ? "–" : `${Math.round(draft.confidence * 100)}%`}
              </td>
              <td className="whitespace-nowrap py-2 text-fg-muted">
                {draft.generated_at ? format.timestamp(draft.generated_at) : "–"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
