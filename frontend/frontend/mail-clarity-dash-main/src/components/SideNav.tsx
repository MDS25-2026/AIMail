import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import { useSession, useTodo } from "../lib/queries";

const NAV_ITEMS = [
  { label: "nav.inbox", to: "/" },
  { label: "nav.todo", to: "/todo" },
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
  // Only with a mailbox: the admin console and a user without one must not ask for a to-do list.
  const session = useSession();
  const todo = useTodo(session.data?.hasMailbox === true);
  const todoCount = todo.data?.count ?? 0;
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
              {item.to === "/todo" && todoCount > 0 ? (
                <span className="ml-2 rounded-full bg-brand px-1.5 text-xs font-semibold text-on-brand">
                  <span className="sr-only">{t("todo.countLabel", { count: todoCount })}</span>
                  <span aria-hidden>{todoCount}</span>
                </span>
              ) : null}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
