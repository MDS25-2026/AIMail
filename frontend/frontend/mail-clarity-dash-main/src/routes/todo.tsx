import { createFileRoute, useNavigate } from "@tanstack/react-router";

import AppShell from "../components/AppShell";
import TodoPage from "../components/TodoPage";
import { Page, pageMeta } from "../lib/pageMeta";
import { parseTab, type TodoTab } from "../lib/todoTabs";

type TodoSearch = { tab?: TodoTab };

export const Route = createFileRoute("/todo")({
  validateSearch: (search: Record<string, unknown>): TodoSearch => ({ tab: parseTab(search.tab) }),
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Todo) }),
  component: TodoRoute,
});

function TodoRoute() {
  const { tab } = Route.useSearch();
  const navigate = useNavigate();
  return (
    <AppShell>
      {/* Replace, not push: switching tabs shouldn't fill the Back button's history. */}
      <TodoPage
        tab={tab}
        onTab={(next) => void navigate({ to: "/todo", search: { tab: next }, replace: true })}
      />
    </AppShell>
  );
}
