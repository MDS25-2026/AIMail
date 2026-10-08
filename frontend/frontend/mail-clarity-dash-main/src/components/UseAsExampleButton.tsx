import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { useAddStyleExample } from "../lib/queries";
import { InlineAlert, InlineStatus } from "./InlineMessages";
import { button } from "./variants";

/** Adds a sent reply to the reader's writing style; the server masks it before storing. */
export default function UseAsExampleButton({ emailId }: { emailId: string }) {
  const { t } = useTranslation();
  const add = useAddStyleExample();
  const error = add.error && errorMessage(add.error, t, "writingStyle.failed");
  if (add.isSuccess) {
    return <InlineStatus size="xs">{t("writingStyle.addedAsExample")}</InlineStatus>;
  }
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => add.mutate({ emailId })}
        disabled={add.isPending}
        className={button({ intent: "quiet", size: "xs" })}
      >
        {t("writingStyle.useAsExample")}
      </button>
      {error ? <InlineAlert size="xs">{error}</InlineAlert> : null}
    </div>
  );
}
