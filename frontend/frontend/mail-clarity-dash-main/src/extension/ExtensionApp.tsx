import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import SidePanel, { PanelHeader } from "../components/SidePanel";
import {
  fetchEmail,
  fetchEmailByThread,
  fetchSession,
  SIGN_IN_URL,
  SignedOutError,
} from "../lib/api";
import { queryKeys } from "../lib/queries";
import { useDraftWorkflow } from "../lib/useDraftWorkflow";
import type { Email } from "../types/email";
import { TabState, useOpenThread } from "./useOpenThread";

// While signed out, check again every couple of seconds, so signing in from the tab takes effect alone.
const SIGNED_OUT_POLL_MS = 2000;

type OpenSignIn = () => void;

/** Opens Google sign-in in a tab, and closes that tab again once the session exists. */
function useSignInTab(isSignedIn: boolean): OpenSignIn {
  const tabId = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!isSignedIn || tabId.current === undefined) return;
    // The reader may have closed it already; that is fine.
    chrome.tabs.remove(tabId.current).catch(() => undefined);
    tabId.current = undefined;
  }, [isSignedIn]);
  return () =>
    void chrome.tabs.create({ url: SIGN_IN_URL }).then((tab) => {
      tabId.current = tab.id;
    });
}

export default function ExtensionApp() {
  const { tab, threadId } = useOpenThread();
  const session = useQuery({
    queryKey: queryKeys.session,
    queryFn: fetchSession,
    retry: false,
    refetchInterval: (query) =>
      query.state.error instanceof SignedOutError ? SIGNED_OUT_POLL_MS : false,
  });
  const openSignIn = useSignInTab(session.isSuccess);

  if (session.error instanceof SignedOutError) return <SignedOut onSignIn={openSignIn} />;
  if (tab === TabState.Loading || session.isPending) return <PanelMessage titleKey="loading" />;
  if (tab === TabState.NotGmail)
    return <PanelMessage titleKey="notGmailTitle" hintKey="notGmailHint" />;
  if (tab === TabState.NeedsReload)
    return <PanelMessage titleKey="reloadTitle" hintKey="reloadHint" />;
  if (threadId === null) return <PanelMessage titleKey="noEmailTitle" hintKey="noEmailHint" />;
  return (
    <ThreadPanel
      key={threadId}
      threadId={threadId}
      account={session.data?.email ?? ""}
      onSignIn={openSignIn}
    />
  );
}

type ThreadPanelProps = { threadId: string; account: string; onSignIn: OpenSignIn };

function ThreadPanel({ threadId, account, onSignIn }: ThreadPanelProps) {
  const { t } = useTranslation();
  const found = useQuery({
    queryKey: ["email-by-thread", threadId],
    queryFn: () => fetchEmailByThread(threadId),
  });

  if (found.error instanceof SignedOutError) return <SignedOut onSignIn={onSignIn} />;
  if (found.isPending) return <PanelMessage titleKey="preparing" account={account} />;
  if (found.isError) {
    return (
      <PanelMessage titleKey="loadFailed" account={account}>
        <PanelButton onClick={() => void found.refetch()}>{t("draftStatus.retry")}</PanelButton>
      </PanelMessage>
    );
  }
  if (found.data === null)
    return <PanelMessage titleKey="notFoundTitle" hintKey="notFoundHint" account={account} />;
  return <OpenEmail initial={found.data} account={account} />;
}

function OpenEmail({ initial, account }: { initial: Email; account: string }) {
  // Seeded from the lookup and keyed like the dashboard's detail, so every draft action's
  // response (written to this key) updates the panel without another round trip.
  const { data: email } = useQuery({
    queryKey: queryKeys.email(initial.id),
    queryFn: () => fetchEmail(initial.id),
    initialData: initial,
    staleTime: Infinity,
  });
  const workflow = useDraftWorkflow(email);
  return (
    <SidePanel
      email={email}
      account={account}
      draft={workflow.draft}
      tone={workflow.tone}
      onDraftChange={workflow.setDraft}
      onToneChange={(_emailId, tone) => workflow.regenerate(tone)}
      onRegenerate={() => workflow.regenerate()}
      onRefine={(_emailId, instruction) => workflow.refine(instruction)}
      onApproveSend={workflow.send}
      isRegenerating={workflow.isRegenerating}
      isRefining={workflow.isRefining}
      isSending={workflow.isSending}
      status={{
        ...workflow.status,
        isGenerating: false,
        isLoadFailed: false,
        onRetryLoad: () => undefined,
      }}
    />
  );
}

function SignedOut({ onSignIn }: { onSignIn: OpenSignIn }) {
  const { t } = useTranslation();
  return (
    <PanelMessage titleKey="signedOutTitle" hintKey="signedOutHint">
      <PanelButton onClick={onSignIn}>{t("signIn.google")}</PanelButton>
    </PanelMessage>
  );
}

type MessageKey =
  | "loading"
  | "preparing"
  | "loadFailed"
  | "notGmailTitle"
  | "reloadTitle"
  | "noEmailTitle"
  | "notFoundTitle"
  | "signedOutTitle";
type HintKey = "notGmailHint" | "reloadHint" | "noEmailHint" | "notFoundHint" | "signedOutHint";

function PanelMessage({
  titleKey,
  hintKey,
  account,
  children,
}: {
  titleKey: MessageKey;
  hintKey?: HintKey;
  account?: string;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex h-full flex-col bg-surface-muted">
      <PanelHeader account={account} />
      <div
        role="status"
        className="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center"
      >
        <p className="text-sm font-semibold text-fg-body">{t(`extension.${titleKey}`)}</p>
        {hintKey ? (
          <p className="max-w-xs text-sm text-fg-muted">
            {t(`extension.${hintKey}`, { account: account ?? "" })}
          </p>
        ) : null}
        {children}
      </div>
    </div>
  );
}

function PanelButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mt-2 rounded-md bg-brand px-4 py-2 text-sm font-semibold text-on-brand hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
    >
      {children}
    </button>
  );
}
