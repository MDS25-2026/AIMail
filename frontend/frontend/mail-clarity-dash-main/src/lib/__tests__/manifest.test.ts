import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "vitest";

const PUBLIC = resolve(__dirname, "../../../public");

type Manifest = {
  display: string;
  start_url: string;
  icons: { src: string; sizes: string; purpose?: string }[];
};

test("the install manifest opens standalone and every icon it names exists", () => {
  const manifest: Manifest = JSON.parse(readFileSync(`${PUBLIC}/manifest.webmanifest`, "utf8"));
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  expect(manifest.icons.map((icon) => icon.sizes)).toEqual(["192x192", "512x512", "512x512"]);
  expect(manifest.icons.some((icon) => icon.purpose === "maskable")).toBe(true);
  for (const icon of manifest.icons) expect(existsSync(`${PUBLIC}${icon.src}`)).toBe(true);
});
