import { Link } from "@tanstack/react-router";
import { CircleCheck, CircleX, TriangleAlert } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import type { PartState, ServiceStatus } from "../lib/api/status";
import { useServiceStatus } from "../lib/queries";
import { cn } from "../lib/utils";

type ServerPart = keyof ServiceStatus["parts"];

const SERVER_PARTS: readonly ServerPart[] = [
  "backend",
  "database",
  "masking",
  "drafting",
  "listener",
];

const STATE_LOOK: Record<PartState, { icon: LucideIcon; tone: string }> = {
  ok: { icon: CircleCheck, tone: "text-success" },
  degraded: { icon: TriangleAlert, tone: "text-warning" },
  down: { icon: CircleX, tone: "text-danger" },
};

const TICK_MS = 1_000;

/** Seconds since the last answer, ticking, so "checked 20 s ago" stays true while the page sits open. */
function useSecondsSince(time: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), TICK_MS);
    return () => window.clearInterval(timer);
  }, []);
  return Math.max(0, Math.round((now - time) / TICK_MS));
}

/** Public: whether each part of AIMail works (specs/features/todo-redesign-and-status.md). */
export default function StatusPage() {
  const { t } = useTranslation();
  const status = useServiceStatus();
  const seconds = useSecondsSince(Math.max(status.dataUpdatedAt, status.errorUpdatedAt));
  // No answer at all means the backend is down, and so is everything it was going to report on.
  const stateOf = (part: ServerPart): PartState | null => {
    if (status.isError) return "down";
    return status.data?.parts[part] ?? null;
  };
  return (
    <div className="min-h-dvh bg-app text-fg-body">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <Link to="/signin" className="text-lg font-semibold tracking-tight text-fg">
            {t("app.name")}
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-8 sm:px-6">
        <h1 className="text-2xl font-semibold text-fg">{t("serviceStatus.title")}</h1>
        <p className="text-sm text-fg-muted">{t("serviceStatus.intro")}</p>
        <ul className="divide-y divide-line rounded-lg border border-line bg-surface">
          {/* The page loaded, so the dashboard itself is answering. */}
          <PartRow name={t("serviceStatus.parts.dashboard")} state="ok" />
          {SERVER_PARTS.map((part) => (
            <PartRow key={part} name={t(`serviceStatus.parts.${part}`)} state={stateOf(part)} />
          ))}
        </ul>
        <p className="text-xs text-fg-subtle">
          {status.isPending
            ? t("serviceStatus.checking")
            : t("serviceStatus.checkedAgo", { count: seconds })}
        </p>
      </main>
    </div>
  );
}

function PartRow({ name, state }: { name: string; state: PartState | null }) {
  const { t } = useTranslation();
  const label = <span className="text-sm font-medium text-fg">{name}</span>;
  if (!state) {
    return (
      <li className="flex items-center justify-between gap-4 px-4 py-3">
        {label}
        <span className="text-sm text-fg-subtle">{t("serviceStatus.checking")}</span>
      </li>
    );
  }
  const { icon: Icon, tone } = STATE_LOOK[state];
  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3">
      {label}
      <span className={cn("flex items-center gap-1.5 text-sm font-medium", tone)}>
        <Icon aria-hidden className="size-4" />
        {t(`serviceStatus.states.${state}`)}
      </span>
    </li>
  );
}
