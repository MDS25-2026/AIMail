import { useTranslation } from "react-i18next";

import { fieldEntries } from "../../lib/auditTrail";
import type { AuditFields } from "../../types/audit";

/** A record's fields as key and value, exactly as stored. */
export default function FieldList({ fields }: { fields: AuditFields }) {
  const { t } = useTranslation();
  const entries = fieldEntries(fields);
  if (entries.length === 0) return <span className="text-fg-subtle">{t("audit.noFields")}</span>;
  return (
    <dl className="flex flex-wrap gap-x-3 gap-y-0.5">
      {entries.map(([key, value]) => (
        <div key={key} className="flex min-w-0 gap-1">
          <dt className="font-mono text-fg-subtle">{key}</dt>
          <dd className="break-all text-fg-body">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
