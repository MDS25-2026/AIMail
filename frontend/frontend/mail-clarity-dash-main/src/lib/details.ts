import type { Detail } from "../types/email";
import { placeholderPattern } from "./masking";

/**
 * Restorable masking (specs/features/restorable-masking.md): stored text carries placeholders such
 * as [PERSON_1], and detail responses list the real values. These helpers show the owner the real
 * details; nothing here ever sends a value anywhere.
 */

export type DetailValues = ReadonlyMap<string, string>;

export const NO_DETAILS: DetailValues = new Map();

export function detailValues(details: readonly Detail[] | undefined): DetailValues {
  return new Map((details ?? []).map((detail) => [detail.placeholder, detail.value]));
}

/** Text with every known placeholder filled in; unknown ones stay as written. */
export function restoreDetails(text: string, values: DetailValues): string {
  return text.replace(
    placeholderPattern(),
    (placeholder) => values.get(placeholder) ?? placeholder,
  );
}

export type Segment = { text: string; isDetail: boolean };

/** The text split so each restored detail can be marked as hidden from the AI. */
export function detailSegments(text: string, values: DetailValues): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(placeholderPattern())) {
    const value = values.get(match[0]);
    if (value === undefined || match.index === undefined) continue;
    if (match.index > last) segments.push({ text: text.slice(last, match.index), isDetail: false });
    segments.push({ text: value, isDetail: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), isDetail: false });
  return segments;
}

/** Placeholders the reader cannot see filled in: the vault expired or would not open. */
export function hasMissingDetails(text: string, values: DetailValues): boolean {
  return [...text.matchAll(placeholderPattern())].some((match) => !values.has(match[0]));
}

export const DETAIL_MARK_CLASS = "rounded-sm bg-brand-soft px-0.5 text-fg";

/**
 * Restores details inside already-sanitised HTML. Values go in only as text nodes and attribute
 * values, never as markup, so a "name" in an email cannot inject anything.
 */
export function restoreDetailsInHtml(html: string, values: DetailValues, title: string): string {
  if (values.size === 0) return html;
  const doc = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html");
  const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
  const texts: Text[] = [];
  while (walker.nextNode()) texts.push(walker.currentNode as Text);
  for (const node of texts) replaceInTextNode(doc, node, values, title);
  for (const element of doc.body.querySelectorAll("[href]")) {
    element.setAttribute("href", restoreDetails(element.getAttribute("href") ?? "", values));
  }
  return doc.body.innerHTML;
}

function replaceInTextNode(doc: Document, node: Text, values: DetailValues, title: string): void {
  const segments = detailSegments(node.data, values);
  if (!segments.some((segment) => segment.isDetail)) return;
  const fragment = doc.createDocumentFragment();
  for (const segment of segments) {
    if (!segment.isDetail) {
      fragment.append(segment.text);
      continue;
    }
    const mark = doc.createElement("mark");
    mark.className = DETAIL_MARK_CLASS;
    mark.title = title;
    mark.textContent = segment.text;
    fragment.append(mark);
  }
  node.replaceWith(fragment);
}
