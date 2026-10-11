import { createFileRoute } from "@tanstack/react-router";

import AppShell from "../components/AppShell";
import TodoPage from "../components/TodoPage";
import { Page, pageMeta } from "../lib/pageMeta";

export const Route = createFileRoute("/todo")({
  head: ({ match }) => ({ meta: pageMeta(match.context.preferences.language, Page.Todo) }),
  component: TodoRoute,
});

function TodoRoute() {
  return (
    <AppShell>
      <TodoPage />
    </AppShell>
  );
}
