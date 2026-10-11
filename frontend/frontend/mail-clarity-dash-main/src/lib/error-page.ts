import { en } from "../locales/en";
import { ms } from "../locales/ms";
import { zh } from "../locales/zh";
import { Language, parsePreferences } from "./preferences";

// Rendered outside React (the app itself failed), so the words come straight from the locales.
const WORDS = {
  [Language.English]: en.errorPage,
  [Language.Malay]: ms.errorPage,
  [Language.Chinese]: zh.errorPage,
};

function cookieFrom(header: string | null): (name: string) => string | undefined {
  const pairs = (header ?? "").split(";").map((pair) => pair.trim().split("="));
  return (name) => {
    const value = pairs.find(([key]) => key === name)?.[1];
    try {
      return value === undefined ? undefined : decodeURIComponent(value);
    } catch {
      return undefined; // a malformed value is just "not set"
    }
  };
}

/** The error page in the reader's language (the language cookie), English when there is none. */
export function errorPageResponse(request: Request): Response {
  const { language } = parsePreferences(cookieFrom(request.headers.get("cookie")));
  return new Response(renderErrorPage(language), {
    status: 500,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
}

export function renderErrorPage(language: Language): string {
  const words = WORDS[language];
  return `<!doctype html>
<html lang="${language}">
  <head>
    <meta charset="utf-8" />
    <title>${words.title}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>
      body { font: 15px/1.5 system-ui, -apple-system, sans-serif; background: #fafafa; color: #111; display: grid; place-items: center; min-height: 100vh; margin: 0; padding: 1.5rem; }
      .card { max-width: 28rem; width: 100%; text-align: center; padding: 2rem; }
      h1 { font-size: 1.25rem; margin: 0 0 0.5rem; }
      p { color: #4b5563; margin: 0 0 1.5rem; }
      .actions { display: flex; gap: 0.5rem; justify-content: center; flex-wrap: wrap; }
      a, button { padding: 0.5rem 1rem; border-radius: 0.375rem; font: inherit; cursor: pointer; text-decoration: none; border: 1px solid transparent; }
      .primary { background: #111; color: #fff; }
      .secondary { background: #fff; color: #111; border-color: #d1d5db; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>${words.title}</h1>
      <p>${words.body}</p>
      <div class="actions">
        <button class="primary" onclick="location.reload()">${words.retry}</button>
        <a class="secondary" href="/">${words.home}</a>
      </div>
    </div>
  </body>
</html>`;
}
