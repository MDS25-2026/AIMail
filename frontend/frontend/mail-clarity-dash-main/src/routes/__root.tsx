import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import type { ErrorComponentProps } from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import appCss from "../styles.css?url";
import PreferencesProvider from "../components/PreferencesProvider";
import { button } from "../components/variants";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { Page, pageMeta } from "../lib/pageMeta";
import { coloursAttribute, SYSTEM_THEME_SCRIPT, Theme } from "../lib/preferences";
import { readPreferences } from "../lib/readPreferences";
import { cn } from "../lib/utils";

function NotFoundComponent() {
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

function ErrorComponent({ error, reset }: ErrorComponentProps) {
  const { t } = useTranslation();
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-app px-4">
      <div className="max-w-md text-center">
        <h1 className="text-xl font-semibold tracking-tight text-fg">{t("page.crashTitle")}</h1>
        <p className="mt-2 text-sm text-fg-muted">{t("page.crashBody")}</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className={cn(
              button({ intent: "primary", size: "md" }),
              "inline-flex items-center justify-center",
            )}
          >
            {t("page.tryAgain")}
          </button>
          <a
            href="/"
            className={cn(button({ size: "md" }), "inline-flex items-center justify-center")}
          >
            {t("page.goHome")}
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  // Cookie-backed, so the server renders the reader's theme and language on the first paint.
  beforeLoad: () => ({ preferences: readPreferences() }),
  head: ({ match }) => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      ...pageMeta(match.context.preferences.language, Page.App),
    ],
    links: [
      {
        rel: "stylesheet",
        href: appCss,
      },
      { rel: "icon", href: "/favicon.ico", type: "image/x-icon" },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

function RootShell({ children }: { children: ReactNode }) {
  const { preferences } = Route.useRouteContext();
  return (
    // suppressHydrationWarning: under "system" the inline script may add the dark class before
    // React hydrates, which is the point of it.
    <html
      lang={preferences.language}
      className={preferences.theme === Theme.Dark ? "dark" : undefined}
      data-colours={coloursAttribute(preferences.colours)}
      suppressHydrationWarning
    >
      <head>
        <HeadContent />
        {preferences.theme === Theme.System ? (
          <script dangerouslySetInnerHTML={{ __html: SYSTEM_THEME_SCRIPT }} />
        ) : null}
      </head>
      <body>
        {/* In the shell, not the root component, so the 404 and error pages are translated too. */}
        <PreferencesProvider initial={preferences}>{children}</PreferencesProvider>
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      {/* Required: nested routes render here. Removing <Outlet /> breaks all child routes. */}
      <Outlet />
    </QueryClientProvider>
  );
}
