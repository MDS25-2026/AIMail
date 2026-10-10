import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

const NAV_ITEMS = [
  { label: "nav.inbox", to: "/" },
  { label: "nav.drafts", to: "/drafts" },
  { label: "nav.sent", to: "/sent" },
  { label: "nav.scheduled", to: "/scheduled" },
  { label: "nav.knowledge", to: "/knowledge" },
  { label: "nav.audit", to: "/audit" },
  { label: "nav.settings", to: "/settings" },
  { label: "nav.admin", to: "/admin" },
] as const;

const BASE_ITEM = "block w-full rounded-md px-3 py-2 text-left text-sm";

export default function SideNav() {
  const { t } = useTranslation();
  return (
    <nav aria-label={t("nav.label")} className="w-44 shrink-0 bg-rail p-3">
      <ul className="space-y-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <Link
              to={item.to}
              // Without exact, "/" would match every route and light up permanently.
              activeOptions={{ exact: item.to === "/" }}
              className={`${BASE_ITEM} text-rail-fg hover:bg-rail-hover hover:text-on-rail`}
              activeProps={{ className: `${BASE_ITEM} bg-rail-active font-semibold text-on-rail` }}
            >
              {t(item.label)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
