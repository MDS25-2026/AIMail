import { Link } from "@tanstack/react-router";
import { Inbox, ListTodo, Send, Settings } from "lucide-react";
import { useTranslation } from "react-i18next";

import { useSession, useTodo } from "../lib/queries";

const ITEMS = [
  { label: "nav.inbox", to: "/", Icon: Inbox },
  { label: "nav.todo", to: "/todo", Icon: ListTodo },
  { label: "nav.sent", to: "/sent", Icon: Send },
  { label: "nav.settings", to: "/settings", Icon: Settings },
] as const;

const ITEM = "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-[11px]";

/** The phone's navigation (specs/features/mobile-layout.md); the side rail takes over from md up. */
export default function BottomNav() {
  const { t } = useTranslation();
  const session = useSession();
  const todo = useTodo(session.data?.hasMailbox === true);
  const todoCount = todo.data?.count ?? 0;
  return (
    <nav
      aria-label={t("nav.label")}
      // Clear of the home indicator on a notched phone, with viewport-fit=cover in the root head.
      className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul className="flex">
        {ITEMS.map(({ label, to, Icon }) => (
          <li key={to} className="flex flex-1">
            <Link
              to={to}
              activeOptions={{ exact: to === "/" }}
              className={`${ITEM} text-fg-muted`}
              activeProps={{
                className: `${ITEM} font-semibold text-brand`,
                "aria-current": "page",
              }}
            >
              <span className="relative">
                <Icon aria-hidden className="size-5" />
                {to === "/todo" && todoCount > 0 ? (
                  <span className="absolute -right-2.5 -top-1.5 rounded-full bg-brand px-1 text-[10px] font-semibold text-on-brand">
                    <span className="sr-only">{t("todo.countLabel", { count: todoCount })}</span>
                    <span aria-hidden>{todoCount}</span>
                  </span>
                ) : null}
              </span>
              {t(label)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
