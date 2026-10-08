import { useTranslation } from "react-i18next";

import { button } from "./variants";

type LoadOlderEmailsProps = {
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  fetchNextPage: () => unknown;
};

/** The inbox comes a page at a time; this loads the next, older one. Hidden on the last page. */
export default function LoadOlderEmails({
  hasNextPage,
  isFetchingNextPage,
  fetchNextPage,
}: LoadOlderEmailsProps) {
  const { t } = useTranslation();
  if (!hasNextPage) return null;
  return (
    <div className="flex justify-center p-3">
      <button
        type="button"
        disabled={isFetchingNextPage}
        onClick={() => void fetchNextPage()}
        className={button({ size: "sm" })}
      >
        {isFetchingNextPage ? t("inbox.loadingMore") : t("inbox.loadMore")}
      </button>
    </div>
  );
}
