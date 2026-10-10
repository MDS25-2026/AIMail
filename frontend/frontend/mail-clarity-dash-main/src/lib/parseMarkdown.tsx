import type { ReactNode } from "react";

function sanitizeLinkHref(rawUrl: string): string | null {
  const trimmed = rawUrl.trim();
  if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed) || /^\/[^/\\]/.test(trimmed)) {
    try {
      if (/^https?:\/\//i.test(trimmed)) {
        const parsed = new URL(trimmed);
        if (parsed.protocol === "http:" || parsed.protocol === "https:") {
          return parsed.href;
        }
      } else {
        return encodeURI(trimmed);
      }
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Parses inline markdown tokens:
 * - **bold** or __bold__ -> <strong>
 * - *italic* or _italic_ -> <em>
 * - `code` -> <code>
 * - [label](url) -> <a>
 */
export function parseInlineTokens(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // Token match for inline code, bold, italic, and links
  const regex = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|\[[^\]]+\]\([^)]+\))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }

    const token = match[0];
    if (token.startsWith("`") && token.endsWith("`")) {
      nodes.push(
        <code
          key={match.index}
          className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[11px] text-brand"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (
      (token.startsWith("**") && token.endsWith("**")) ||
      (token.startsWith("__") && token.endsWith("__"))
    ) {
      nodes.push(
        <strong key={match.index} className="font-semibold text-fg">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (
      (token.startsWith("*") && token.endsWith("*")) ||
      (token.startsWith("_") && token.endsWith("_"))
    ) {
      nodes.push(
        <em key={match.index} className="italic text-fg">
          {token.slice(1, -1)}
        </em>,
      );
    } else if (token.startsWith("[") && token.includes("](")) {
      const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      const safeHref = linkMatch ? sanitizeLinkHref(linkMatch[2]) : null;
      if (linkMatch && safeHref) {
        nodes.push(
          <a
            key={match.index}
            href={safeHref}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand underline hover:text-brand-hover"
          >
            {linkMatch[1]}
          </a>,
        );
      } else if (linkMatch) {
        nodes.push(linkMatch[1]);
      } else {
        nodes.push(token);
      }
    } else {
      nodes.push(token);
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes;
}
