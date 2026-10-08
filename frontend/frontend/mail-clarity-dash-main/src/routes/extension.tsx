import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import SidePanel from "../components/SidePanel";
import { PageEmpty, PageError, PageLoading } from "../components/PageState";
import { Page, pageMeta } from "../lib/pageMeta";
import { useEmail, useEmails } from "../lib/queries";
import { useDraftWorkflow } from "../lib/useDraftWorkflow";

export const Route = createFileRoute("/extension")({
  head: ({ match }) => ({
    meta: [
      ...pageMeta(match.context.preferences.language, Page.Extension),
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: ExtensionPage,
});

/**
 * Preview of the condensed panel the Chrome extension renders inside Gmail.
 *
 * Runs on a real email rather than a fixture: the panel is the surface that will be wired to
 * this API, so previewing it against fabricated content proved nothing and put a fake sender
 * on screen during demos. Same page, same layout — the data and the buttons are now real.
 */
function ExtensionPage() {
  const { t } = useTranslation();
  const emails = useEmails();
  // Prefer an email that already has a draft, so the panel previews a filled-in state rather
  // than an empty one; fall back to the newest email when nothing has been generated yet.
  const candidate = emails.data?.find((item) => item.draftReply) ?? emails.data?.[0] ?? null;
  const selected = useEmail(candidate?.id ?? null);
  const email = selected.data ?? candidate;

  const workflow = useDraftWorkflow(email, selected);

  return (
    <div className="min-h-screen bg-app p-8">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-sm font-semibold text-fg-body">{t("extension.heading")}</h1>
        <Link to="/" className="text-sm font-medium text-brand hover:text-brand-strong">
          {t("extension.back")}
        </Link>
      </div>
      <div className="relative h-[720px] w-[390px] overflow-hidden rounded-lg border border-line">
        {emails.isPending ? <PageLoading label={t("extension.label")} /> : null}
        {emails.isError ? <PageError label={t("extension.label")} error={emails.error} /> : null}
        {emails.data && !email ? (
          <PageEmpty title={t("extension.emptyTitle")} hint={t("extension.emptyHint")} />
        ) : null}
        {email ? <SidePanel email={email} workflow={workflow} /> : null}
      </div>
    </div>
  );
}
