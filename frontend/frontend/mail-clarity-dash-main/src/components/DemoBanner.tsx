import { useNavigate } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";

import { useIsDemo } from "../demo/mode";
import { SIGN_IN_URL } from "../lib/api/config";
import { useDemoSwitch } from "../lib/queries";
import { button } from "./variants";

/** On every dashboard page in the demo: what this is, and the two ways out (#227). */
export default function DemoBanner() {
  const { t } = useTranslation();
  const isDemo = useIsDemo();
  const { leave } = useDemoSwitch();
  const navigate = useNavigate();
  if (!isDemo) return null;

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 border-b border-info-line bg-info-soft px-4 py-2 text-sm text-fg md:px-6"
    >
      <span>{t("demo.banner")}</span>
      <div className="flex flex-wrap items-center gap-2">
        <a href={SIGN_IN_URL} onClick={leave} className={button({ intent: "primary", size: "sm" })}>
          {t("demo.signIn")}
        </a>
        <button
          type="button"
          onClick={() => {
            leave();
            void navigate({ to: "/signin" });
          }}
          className={button({ size: "sm" })}
        >
          {t("demo.leave")}
        </button>
      </div>
    </div>
  );
}
