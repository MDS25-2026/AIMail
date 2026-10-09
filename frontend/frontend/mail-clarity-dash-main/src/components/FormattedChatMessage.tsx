import { Fragment, type ReactNode } from "react";

type FormattedChatMessageProps = {
  content: string;
  className?: string;
};

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
      if (linkMatch) {
        nodes.push(
          <a
            key={match.index}
            href={linkMatch[2]}
            target="_blank"
            rel="noopener noreferrer"
            className="text-brand underline hover:text-brand-hover"
          >
            {linkMatch[1]}
          </a>,
        );
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

export type ListItem = {
  num?: string;
  title: string;
  detail?: string;
};

type Block =
  | { type: "heading"; level: number; content: string }
  | { type: "paragraph"; content: string }
  | { type: "ul"; items: ListItem[] }
  | { type: "ol"; items: ListItem[] }
  | { type: "quote"; content: string }
  | { type: "code"; code: string };

/**
 * Structured markdown renderer for AI assistant messages.
 * Formats lists, key metrics, bold emphasis, and code blocks cleanly
 * without raw markdown syntax leaks (such as asterisks or dashes).
 */
export default function FormattedChatMessage({ content, className }: FormattedChatMessageProps) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];

  let i = 0;
  while (i < lines.length) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Code block check
    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // Skip closing ```
      blocks.push({ type: "code", code: codeLines.join("\n") });
      continue;
    }

    // Headings: ###, ##, #
    const headingMatch = /^(#{1,4})\s+(.+)$/.exec(trimmed);
    if (headingMatch) {
      blocks.push({
        type: "heading",
        level: headingMatch[1].length,
        content: headingMatch[2],
      });
      i++;
      continue;
    }

    // Blockquote: >
    if (trimmed.startsWith("> ")) {
      blocks.push({
        type: "quote",
        content: trimmed.slice(2).trim(),
      });
      i++;
      continue;
    }

    // Unordered list: - or *
    if (/^[-*]\s+/.test(trimmed)) {
      const items: ListItem[] = [];
      while (i < lines.length) {
        const lineTrim = lines[i].trim();
        if (/^[-*]\s+/.test(lineTrim)) {
          const title = lineTrim.replace(/^[-*]\s+/, "");
          i++;
          const detailLines: string[] = [];
          while (
            i < lines.length &&
            lines[i].trim() &&
            !/^[-*]\s+/.test(lines[i].trim()) &&
            !/^\d+\.\s+/.test(lines[i].trim()) &&
            !lines[i].trim().startsWith("```") &&
            !/^#{1,4}\s+/.test(lines[i].trim()) &&
            !lines[i].trim().startsWith("> ")
          ) {
            detailLines.push(lines[i].trim());
            i++;
          }
          items.push({
            title,
            detail: detailLines.length > 0 ? detailLines.join(" ") : undefined,
          });
        } else if (!lineTrim) {
          // Check if after blank lines, another bullet continues this list
          let peek = i + 1;
          while (peek < lines.length && !lines[peek].trim()) {
            peek++;
          }
          if (peek < lines.length && /^[-*]\s+/.test(lines[peek].trim())) {
            i = peek;
          } else {
            break;
          }
        } else {
          break;
        }
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    // Ordered list: 1., 2.
    if (/^\d+\.\s+/.test(trimmed)) {
      const items: ListItem[] = [];
      while (i < lines.length) {
        const lineTrim = lines[i].trim();
        const numMatch = /^(\d+)\.\s+(.+)$/.exec(lineTrim);
        if (numMatch) {
          const num = numMatch[1];
          const title = numMatch[2];
          i++;
          const detailLines: string[] = [];
          while (
            i < lines.length &&
            lines[i].trim() &&
            !/^[-*]\s+/.test(lines[i].trim()) &&
            !/^\d+\.\s+/.test(lines[i].trim()) &&
            !lines[i].trim().startsWith("```") &&
            !/^#{1,4}\s+/.test(lines[i].trim()) &&
            !lines[i].trim().startsWith("> ")
          ) {
            detailLines.push(lines[i].trim());
            i++;
          }
          items.push({
            num,
            title,
            detail: detailLines.length > 0 ? detailLines.join(" ") : undefined,
          });
        } else if (!lineTrim) {
          let peek = i + 1;
          while (peek < lines.length && !lines[peek].trim()) {
            peek++;
          }
          if (peek < lines.length && /^\d+\.\s+/.test(lines[peek].trim())) {
            i = peek;
          } else {
            break;
          }
        } else {
          break;
        }
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    // Standard paragraph: combine consecutive non-empty plain lines
    const pLines: string[] = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].trim().startsWith("```") &&
      !/^#{1,4}\s+/.test(lines[i].trim()) &&
      !lines[i].trim().startsWith("> ") &&
      !/^[-*]\s+/.test(lines[i].trim()) &&
      !/^\d+\.\s+/.test(lines[i].trim())
    ) {
      pLines.push(lines[i].trim());
      i++;
    }
    blocks.push({ type: "paragraph", content: pLines.join(" ") });
  }

  return (
    <div className={className ?? "space-y-2 text-xs"}>
      {blocks.map((block, idx) => {
        switch (block.type) {
          case "heading":
            return (
              <h4
                key={idx}
                className="mt-2 text-xs font-semibold tracking-wide text-fg first:mt-0"
              >
                {parseInlineTokens(block.content)}
              </h4>
            );

          case "paragraph":
            return (
              <p key={idx} className="leading-relaxed text-fg">
                {parseInlineTokens(block.content)}
              </p>
            );

          case "ul":
            return (
              <ul key={idx} className="my-2 space-y-2.5 pl-0.5">
                {block.items.map((item, itemIdx) => (
                  <li key={itemIdx} className="flex items-start gap-2 leading-relaxed">
                    <span
                      aria-hidden="true"
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand/80"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-fg leading-snug">{parseInlineTokens(item.title)}</div>
                      {item.detail ? (
                        <div className="mt-1 pl-0.5 text-[11px] leading-relaxed text-fg-muted">
                          {parseInlineTokens(item.detail)}
                        </div>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            );

          case "ol":
            return (
              <ol key={idx} className="my-2 space-y-2.5 pl-0.5">
                {block.items.map((item, itemIdx) => (
                  <li key={itemIdx} className="flex items-start gap-2 leading-relaxed">
                    <span className="shrink-0 font-semibold text-brand text-[11px] min-w-[14px]">
                      {item.num ?? itemIdx + 1}.
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-fg leading-snug">{parseInlineTokens(item.title)}</div>
                      {item.detail ? (
                        <div className="mt-1 pl-0.5 text-[11px] leading-relaxed text-fg-muted">
                          {parseInlineTokens(item.detail)}
                        </div>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ol>
            );

          case "quote":
            return (
              <blockquote
                key={idx}
                className="my-1.5 border-l-2 border-brand/50 pl-2.5 text-xs italic text-fg-muted"
              >
                {parseInlineTokens(block.content)}
              </blockquote>
            );

          case "code":
            return (
              <pre
                key={idx}
                className="my-1.5 overflow-x-auto rounded-md bg-surface-muted p-2 font-mono text-[11px] text-fg"
              >
                <code>{block.code}</code>
              </pre>
            );

          default:
            return null;
        }
      })}
    </div>
  );
}
