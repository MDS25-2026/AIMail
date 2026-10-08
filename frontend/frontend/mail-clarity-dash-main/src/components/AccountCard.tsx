import { useNavigate } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useDeleteAccount, useDisconnectGmail, useSession } from "../lib/queries";
import { cn } from "../lib/utils";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./ui/alert-dialog";
import { InlineAlert, InlineStatus } from "./InlineMessages";
import { button, field } from "./variants";

const DANGER_BUTTON = button({ intent: "danger" });
const CONFIRM_BUTTON = button({ intent: "dangerSolid" });

/** Settings > Account: disconnect Gmail, or delete everything (specs/features/per-user-mailboxes.md). */
export default function AccountCard() {
  const { t } = useTranslation();
  const session = useSession();
  if (!session.data) return null;
  return (
    <section className="space-y-4 rounded-lg border border-line bg-surface p-4">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-fg-subtle">
        {t("account.title")}
      </h2>
      <p className="text-sm text-fg-muted">
        {t("account.signedInAs", { email: session.data.email })}
      </p>
      {session.data.hasMailbox ? <DisconnectGmail /> : null}
      <DeleteAccount email={session.data.email} />
    </section>
  );
}

function DisconnectGmail() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const disconnect = useDisconnectGmail();
  return (
    <AccountAction
      title={t("account.disconnectTitle")}
      body={t("account.disconnectBody")}
      buttonLabel={t("account.disconnect")}
      isOpen={isOpen}
      onOpenChange={setIsOpen}
      isPending={disconnect.isPending}
      error={disconnect.isError ? t("account.disconnectFailed") : null}
      onConfirm={() => disconnect.mutate(undefined, { onSuccess: () => setIsOpen(false) })}
      done={disconnect.isSuccess ? t("account.disconnected") : null}
    />
  );
}

function DeleteAccount({ email }: { email: string }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const remove = useDeleteAccount(() => void navigate({ to: "/signin" }));
  // Typing the address is the confirmation: nothing about it can be undone.
  const isConfirmed = typed.trim().toLowerCase() === email.toLowerCase();
  return (
    <AccountAction
      title={t("account.deleteTitle")}
      body={t("account.deleteBody")}
      buttonLabel={t("account.delete")}
      isOpen={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open);
        setTyped("");
      }}
      isPending={remove.isPending}
      isConfirmDisabled={!isConfirmed}
      error={remove.isError ? t("account.deleteFailed") : null}
      onConfirm={() => remove.mutate()}
    >
      <label className="block space-y-1 text-sm text-fg-body">
        <span>{t("account.deleteTypeEmail", { email })}</span>
        <input
          value={typed}
          onChange={(event) => setTyped(event.target.value)}
          autoComplete="off"
          className={cn(field(), "w-full")}
        />
      </label>
    </AccountAction>
  );
}

type AccountActionProps = {
  title: string;
  body: string;
  buttonLabel: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  isPending: boolean;
  isConfirmDisabled?: boolean;
  error: string | null;
  onConfirm: () => void;
  done?: string | null;
  children?: ReactNode;
};

/** A destructive action behind a confirmation that stays open while it runs and shows a failure. */
function AccountAction(props: AccountActionProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-1">
      <button type="button" className={DANGER_BUTTON} onClick={() => props.onOpenChange(true)}>
        {props.buttonLabel}
      </button>
      {props.done ? <InlineStatus size="xs">{props.done}</InlineStatus> : null}
      <AlertDialog
        open={props.isOpen}
        onOpenChange={(open) => !props.isPending && props.onOpenChange(open)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{props.title}</AlertDialogTitle>
            <AlertDialogDescription className="whitespace-pre-line">
              {props.body}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {props.children}
          {props.error ? <InlineAlert>{props.error}</InlineAlert> : null}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={props.isPending}>{t("account.cancel")}</AlertDialogCancel>
            <button
              type="button"
              className={CONFIRM_BUTTON}
              disabled={props.isPending || props.isConfirmDisabled}
              onClick={props.onConfirm}
            >
              {props.isPending ? t("account.working") : props.buttonLabel}
            </button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
