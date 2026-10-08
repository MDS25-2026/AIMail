import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { errorMessage } from "../lib/api/errors";
import { addStyleExample } from "../lib/api/profile";
import { WRITING_STYLE_KEY } from "../lib/writingStyle";

/** Adds a sent reply to the reader's writing style; the server masks it before storing. */
export default function UseAsExampleButton({ emailId }: { emailId: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const add = useMutation({
    mutationFn: () => addStyleExample({ emailId }),
    onSuccess: (style) => queryClient.setQueryData(WRITING_STYLE_KEY, style),
  });
  const error = add.error && errorMessage(add.error, t, "writingStyle.failed");
  if (add.isSuccess) {
    return (
      <p role="status" className="text-xs text-success">
        {t("writingStyle.addedAsExample")}
      </p>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => add.mutate()}
        disabled={add.isPending}
        className="rounded-md border border-line px-2 py-1 text-xs font-medium text-fg-body hover:bg-surface-muted disabled:opacity-60"
      >
        {t("writingStyle.useAsExample")}
      </button>
      {error ? (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      ) : null}
    </span>
  );
}
