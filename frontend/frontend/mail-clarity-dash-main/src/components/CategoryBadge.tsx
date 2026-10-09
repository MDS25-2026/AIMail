import { Building, Coffee, Handshake, Lock, Package, Users, type LucideIcon } from "lucide-react";
import { useTranslation } from "react-i18next";

import { shownCategory } from "../lib/inboxFilter";
import type { Email, EmailCategory } from "../types/email";

const ICONS: Record<EmailCategory, LucideIcon> = {
  client: Handshake,
  vendor: Package,
  internal: Users,
  security: Lock,
  admin: Building,
  personal: Coffee,
};

/** What kind of email this is, from the classifier (#141). Neutral, so it never competes with the
 *  priority badge; nothing at all when the email is unclassified or the classifier was unsure. */
export default function CategoryBadge({ email }: { email: Email }) {
  const { t } = useTranslation();
  const category = shownCategory(email);
  if (category === null) return null;
  const Icon = ICONS[category];
  return (
    <span className="inline-flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[11px] font-medium text-fg-muted">
      <Icon aria-hidden className="size-3" />
      {t(`category.${category}`)}
    </span>
  );
}
