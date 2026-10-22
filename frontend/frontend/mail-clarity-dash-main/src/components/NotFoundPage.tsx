import { Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import { cn } from "../lib/utils";
import { button } from "./variants";

/** The app's one "page not found": the root route's, and an admin page's to anyone else. */
export default function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-screen items-center justify-center bg-app px-4">
      <div className="max-w-md text-center">
        <h1 className="text-7xl font-bold text-fg">404</h1>
        <h2 className="mt-4 text-xl font-semibold text-fg">{t("page.notFoundTitle")}</h2>
        <p className="mt-2 text-sm text-fg-muted">{t("page.notFoundBody")}</p>
        <div className="mt-6">
          <Link
            to="/"
            className={cn(
              button({ intent: "primary", size: "md" }),
              "inline-flex items-center justify-center",
            )}
          >
            {t("page.goHome")}
          </Link>
        </div>
      </div>
    </div>
  );
}
