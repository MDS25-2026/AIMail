import { CircleCheck, EyeOff, Inbox, PenLine, Send } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { prefersReducedMotion } from "../../lib/motion";
import { cn } from "../../lib/utils";
import { Filled } from "./Redacted";

/** The flow the hero plays, in order; each stage names its caption under `landing.preview`. */
enum Stage {
  Arrives = "arrives",
  Hidden = "hidden",
  Drafted = "drafted",
  Sent = "sent",
}

const STAGES: readonly { stage: Stage; icon: LucideIcon }[] = [
  { stage: Stage.Arrives, icon: Inbox },
  { stage: Stage.Hidden, icon: EyeOff },
  { stage: Stage.Drafted, icon: PenLine },
  { stage: Stage.Sent, icon: Send },
];

const STAGE_MS = 3200;

/** Advances every STAGE_MS unless paused or the reader asked for less motion. */
function useStage(isPaused: boolean): [Stage, (stage: Stage) => void] {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (isPaused || prefersReducedMotion()) return;
    const timer = window.setInterval(() => setIndex((at) => (at + 1) % STAGES.length), STAGE_MS);
    return () => window.clearInterval(timer);
  }, [isPaused]);
  const choose = (stage: Stage) => setIndex(STAGES.findIndex((item) => item.stage === stage));
  return [STAGES[index].stage, choose];
}

/** The hero's working demo: an email hidden, drafted, approved and sent, on a loop. */
export default function LivePreview() {
  const { t } = useTranslation();
  const [isPaused, setIsPaused] = useState(false);
  const [stage, choose] = useStage(isPaused);
  const isHidden = stage === Stage.Hidden || stage === Stage.Drafted;

  return (
    <figure
      className="rounded-xl border border-line bg-surface shadow-lg"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onFocus={() => setIsPaused(true)}
      onBlur={() => setIsPaused(false)}
    >
      <PreviewChrome isHidden={isHidden} />
      <div className="space-y-3 p-4 text-sm">
        <EmailCard isHidden={isHidden} />
        <DraftCard stage={stage} />
      </div>
      <figcaption className="border-t border-line p-3">
        <p aria-live="polite" className="mb-2 text-xs text-fg-muted">
          {t(`landing.preview.captions.${stage}`)}
        </p>
        <StageButtons current={stage} onChoose={choose} />
      </figcaption>
    </figure>
  );
}

function PreviewChrome({ isHidden }: { isHidden: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
      <span className="text-xs font-semibold text-fg">{t("app.name")}</span>
      <span
        className={cn(
          "rounded-full px-2 py-0.5 text-[11px] font-medium transition-colors",
          isHidden ? "bg-brand-soft text-brand" : "bg-surface-muted text-fg-muted",
        )}
      >
        {t(isHidden ? "landing.preview.aiView" : "landing.preview.yourView")}
      </span>
    </div>
  );
}

function EmailCard({ isHidden }: { isHidden: boolean }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1.5 rounded-lg border border-line bg-surface-muted p-3">
      <p className="text-xs text-fg-muted">
        <Filled template="[name] · [email]" isHidden={isHidden} />
      </p>
      <p className="font-semibold text-fg">{t("landing.preview.subject")}</p>
      <p className="leading-relaxed text-fg-body">
        <Filled template={t("landing.preview.body")} isHidden={isHidden} />
      </p>
    </div>
  );
}

function DraftCard({ stage }: { stage: Stage }) {
  const { t } = useTranslation();
  if (stage === Stage.Arrives || stage === Stage.Hidden) {
    return (
      <p className="rounded-lg border border-dashed border-line p-3 text-xs text-fg-subtle">
        {t("landing.preview.waiting")}
      </p>
    );
  }
  const isSent = stage === Stage.Sent;
  return (
    <div className="space-y-2 rounded-lg border border-line p-3 motion-safe:animate-in motion-safe:fade-in">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-semibold text-fg">
          {t(isSent ? "landing.preview.sentTitle" : "landing.preview.draftTitle")}
        </span>
        <span className="inline-flex items-center gap-1 rounded bg-success-soft px-1.5 py-0.5 text-[11px] font-medium text-success">
          <CircleCheck aria-hidden className="size-3" />
          {t(isSent ? "landing.preview.sentBadge" : "landing.preview.checkBadge")}
        </span>
      </div>
      <p className="leading-relaxed text-fg-body">
        <Filled template={t("landing.preview.draft")} isHidden={!isSent} />
      </p>
    </div>
  );
}

function StageButtons({ current, onChoose }: { current: Stage; onChoose: (stage: Stage) => void }) {
  const { t } = useTranslation();
  return (
    <div
      className="grid grid-cols-4 gap-1"
      role="group"
      aria-label={t("landing.preview.stagesLabel")}
    >
      {STAGES.map(({ stage, icon: Icon }) => (
        <button
          key={stage}
          type="button"
          aria-pressed={stage === current}
          onClick={() => onChoose(stage)}
          className={cn(
            "flex min-h-11 flex-col items-center justify-center gap-0.5 rounded-md text-[11px] transition-colors focus-visible:outline-2 focus-visible:outline-brand",
            stage === current
              ? "bg-brand-soft font-semibold text-brand"
              : "text-fg-muted hover:bg-surface-muted",
          )}
        >
          <Icon aria-hidden className="size-4" />
          {t(`landing.preview.stages.${stage}`)}
        </button>
      ))}
    </div>
  );
}
