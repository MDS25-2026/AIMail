import { expect, test } from "vitest";

import { errorPageResponse } from "../error-page";

const page = (cookie?: string) =>
  errorPageResponse(new Request("http://localhost/", cookie ? { headers: { cookie } } : {})).text();

test("the error page speaks the reader's language, from the language cookie", async () => {
  expect(await page("aimail-theme=dark; aimail-lang=ms")).toContain(
    "Halaman ini tidak dapat dimuatkan",
  );
  expect(await page("aimail-lang=zh")).toContain('<html lang="zh">');
  expect(await page("aimail-lang=zh")).toContain("此页面未能加载");
});

test("with no cookie, or one it cannot read, the error page is in English", async () => {
  expect(await page()).toContain("This page didn't load");
  expect(await page("aimail-lang=%E0%A4%A")).toContain("This page didn't load");
});
