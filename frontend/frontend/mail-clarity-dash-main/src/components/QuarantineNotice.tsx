import { ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";

/** Shown instead of the body and the draft while the listener holds content back (#109), or
 *  once it has given up on a message it could never mask. */
export default function QuarantineNotice({ isAbandoned }: { isAbandoned: boolean }) {
  const { t } = useTranslation();
  return (
    <section
      role="status"
      className="flex gap-3 rounded-lg border border-warning-line bg-warning-soft p-4"
    >
      <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-warning" />
      <div>
        <h2 className="text-sm font-semibold text-warning">
          {t(isAbandoned ? "quarantine.abandonedTitle" : "quarantine.title")}
        </h2>
        <p className="mt-1 text-sm text-fg-body">
          {t(isAbandoned ? "quarantine.abandonedBody" : "quarantine.body")}
        </p>
      </div>
    </section>
  );
}
