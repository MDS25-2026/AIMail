import { useTranslation } from "react-i18next";

import { cn } from "../../lib/utils";
import { ActionGroup, AuditWindow, type AuditFilters, type AuditPerson } from "../../types/audit";
import { field } from "../variants";

const GROUPS = Object.values(ActionGroup);
const WINDOWS = Object.values(AuditWindow);
// The "any" choice of a select; never a real group or user id.
const ANY = "";

type AuditFilterBarProps = {
  filters: AuditFilters;
  people: readonly AuditPerson[];
  onChange: (filters: AuditFilters) => void;
};

const SELECT = cn(field({ size: "sm" }), "mt-1 w-full text-xs");
const LABEL = "block min-w-0 text-xs font-medium text-fg-muted";

/** Person, group, failures and time window: each one a query param the backend filters by. */
export default function AuditFilterBar({ filters, people, onChange }: AuditFilterBarProps) {
  const { t } = useTranslation();
  const change = (next: Partial<AuditFilters>) => onChange({ ...filters, ...next });
  return (
    <fieldset className="grid grid-cols-2 gap-3 sm:flex sm:flex-wrap sm:items-end">
      <legend className="sr-only">{t("audit.filters.label")}</legend>
      <label className={cn(LABEL, "sm:w-56")}>
        {t("audit.filters.person")}
        <select
          value={filters.person ?? ANY}
          onChange={(event) => change({ person: event.target.value || null })}
          className={SELECT}
        >
          <option value={ANY}>{t("audit.filters.everyone")}</option>
          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.email}
            </option>
          ))}
        </select>
      </label>
      <label className={cn(LABEL, "sm:w-40")}>
        {t("audit.filters.group")}
        <select
          value={filters.group ?? ANY}
          onChange={(event) =>
            change({ group: GROUPS.find((group) => group === event.target.value) ?? null })
          }
          className={SELECT}
        >
          <option value={ANY}>{t("audit.filters.allGroups")}</option>
          {GROUPS.map((group) => (
            <option key={group} value={group}>
              {t(`audit.groups.${group}`)}
            </option>
          ))}
        </select>
      </label>
      <label className={cn(LABEL, "sm:w-40")}>
        {t("audit.filters.window")}
        <select
          value={filters.window}
          onChange={(event) =>
            change({
              window: WINDOWS.find((window) => window === event.target.value) ?? AuditWindow.All,
            })
          }
          className={SELECT}
        >
          {WINDOWS.map((window) => (
            <option key={window} value={window}>
              {t(`audit.windows.${window}`)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-h-11 items-center gap-2 text-sm font-medium text-fg md:min-h-0 sm:pb-1">
        <input
          type="checkbox"
          checked={filters.isFailuresOnly}
          onChange={(event) => change({ isFailuresOnly: event.target.checked })}
          className="size-4 accent-[var(--brand)]"
        />
        {t("audit.filters.failuresOnly")}
      </label>
    </fieldset>
  );
}
