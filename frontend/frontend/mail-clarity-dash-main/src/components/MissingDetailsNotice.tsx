import { useTranslation } from "react-i18next";

import { hasMissingDetails, detailValues } from "../lib/details";
import type { Email } from "../types/email";

/** Said when placeholders cannot be filled in: the vault expired, or never opened. */
export default function MissingDetailsNotice({ email, draft }: { email: Email; draft: string }) {
  const { t } = useTranslation();
  const values = detailValues(email.details);
  if (!hasMissingDetails(`${email.body}\n${draft}`, values)) return null;
  return (
    <p role="status" className="rounded-md bg-surface-muted px-3 py-2 text-xs text-fg-muted">
      {t("details.unavailable")}
    </p>
  );
}
