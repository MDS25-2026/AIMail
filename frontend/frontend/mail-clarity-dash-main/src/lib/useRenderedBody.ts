import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { restoreDetailsInHtml } from "./details";
import { useDetailValues } from "./detailsContext";
import { useDetailsHidden } from "./detailsVisibility";
import { sanitizeEmailHtml } from "./sanitizeEmail";

const LOOKS_LIKE_HTML = /^\s*<[a-z!]/i;

export type RenderedBody = { html: string | null; blockedImages: number };

/** An email body made safe to show: HTML sanitised, then details restored as text only. Plain
 *  text comes back as html null, to be rendered with WithDetails. */
export function useRenderedBody(body: string, isAllowingImages: boolean): RenderedBody {
  const { t } = useTranslation();
  const values = useDetailValues();
  const [isHidingDetails] = useDetailsHidden();
  const markTitle = t("details.hiddenFromAi");
  return useMemo(() => {
    if (!LOOKS_LIKE_HTML.test(body)) return { html: null, blockedImages: 0 };
    const clean = sanitizeEmailHtml(body, isAllowingImages);
    // After sanitising: details go in as text, so nothing from an email can become markup.
    const html = isHidingDetails ? clean.html : restoreDetailsInHtml(clean.html, values, markTitle);
    return { html, blockedImages: clean.blockedImages };
  }, [body, isAllowingImages, isHidingDetails, values, markTitle]);
}

export function looksLikeHtml(body: string): boolean {
  return LOOKS_LIKE_HTML.test(body);
}
