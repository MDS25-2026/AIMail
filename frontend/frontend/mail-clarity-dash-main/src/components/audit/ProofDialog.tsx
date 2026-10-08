import { Hash, Link as LinkIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { actionLabel } from "../../lib/auditTrail";
import { useFormat } from "../../lib/useFormat";
import { AuditVerification, type AuditTrailEvent } from "../../types/audit";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { button } from "../variants";
import CopyButton from "./CopyButton";
import FieldList from "./FieldList";
import VerificationBadge from "./VerificationBadge";

const CHECK_TEXT = {
  [AuditVerification.Verified]: "audit.modal.verified",
  [AuditVerification.Tampered]: "audit.modal.tampered",
  [AuditVerification.Unverifiable]: "audit.modal.unverifiable",
} as const;

type ProofDialogProps = { event: AuditTrailEvent | null; onClose: () => void };

/** One record's place in the hash chain: what it links back to, and whether its own hash holds. */
export default function ProofDialog({ event, onClose }: ProofDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={event !== null} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="max-w-xl sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{t("audit.modal.title")}</DialogTitle>
          <DialogDescription>{t("audit.modal.subtitle")}</DialogDescription>
        </DialogHeader>
        {event ? <Proof event={event} /> : null}
        <DialogFooter>
          <button type="button" onClick={onClose} className={button({ size: "sm" })}>
            {t("audit.modal.close")}
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Proof({ event }: { event: AuditTrailEvent }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <div className="space-y-4 text-xs">
      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-line bg-surface-muted p-3">
        <Item label={t("audit.modal.recordId")}>
          <span className="break-all font-mono">{event.id}</span>
        </Item>
        <Item label={t("audit.modal.timestamp")}>{format.timestamp(event.createdAt)}</Item>
        <Item label={t("audit.modal.action")}>{actionLabel(event.action, t)}</Item>
        <Item label={t("audit.modal.check")}>
          <VerificationBadge verification={event.verification} />
        </Item>
        <div className="col-span-2">
          <Item label={t("audit.modal.fields")}>
            <FieldList fields={event.fields} />
          </Item>
        </div>
      </dl>
      <p className="text-fg-body">{t(CHECK_TEXT[event.verification])}</p>
      <HashBlock
        icon={<LinkIcon aria-hidden className="size-3.5 text-fg-muted" />}
        label={t("audit.modal.prevHash")}
        hash={event.prevHash}
        // An old row has no link at all; only a checked row without one starts the chain.
        missing={
          event.verification === AuditVerification.Unverifiable
            ? t("audit.modal.noHash")
            : t("audit.modal.firstRecord")
        }
      />
      <div className="rounded-md border border-line px-3 py-2">
        <p className="font-semibold text-fg">{t("audit.modal.formula")}</p>
        <p className="mt-0.5 break-all font-mono text-[10px] text-fg-muted">
          {t("audit.modal.formulaDesc")}
        </p>
      </div>
      <HashBlock
        icon={<Hash aria-hidden className="size-3.5 text-brand" />}
        label={t("audit.modal.currentHash")}
        hash={event.currentHash}
        missing={t("audit.modal.noHash")}
      />
      <p className="rounded border border-line-subtle bg-surface-muted p-3 leading-relaxed text-fg-muted">
        {t("audit.modal.intactMessage")}
      </p>
    </div>
  );
}

function Item({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="font-medium text-fg-muted">{label}</dt>
      <dd className="mt-0.5 text-fg-body">{children}</dd>
    </div>
  );
}

type HashBlockProps = { icon: ReactNode; label: string; hash: string | null; missing: string };

function HashBlock({ icon, label, hash, missing }: HashBlockProps) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 font-semibold text-fg">
          {icon}
          {label}
        </span>
        {hash ? <CopyButton value={hash} name={label} /> : null}
      </div>
      <p className="mt-1 select-all break-all rounded border border-line bg-surface-muted p-2 font-mono text-[11px] text-fg-body">
        {hash ?? missing}
      </p>
    </div>
  );
}
