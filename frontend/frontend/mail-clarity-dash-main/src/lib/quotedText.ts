/** Where a reply's quoted email begins; the same lines listener/sla.go and backend/app/waiting.py cut at. */
const QUOTE_START =
  /^(?:>|-{2,}\s*Original Message|From:\s|Sent:\s|On .*wrote:\s*$|Pada .*(?:menulis|tulis):\s*$|.*写道[:：]\s*$)/i;
// A client may wrap "On Tue, 7 Oct 2026, Aisyah <a@b.c>" and "wrote:" over two lines.
const WRAPPED_HEADER_START = /^(?:On|Pada)\s/i;
const HEADER_END = /(?:wrote|menulis|tulis):\s*$|写道[:：]\s*$/i;

export type SplitBody = { own: string; quoted: string };

/** The sender's new text, and the earlier email they quoted beneath it ("" when none). A body that
 *  is all quote (a forward) is shown whole, so nothing is ever hidden behind an empty message. */
export function splitQuoted(body: string): SplitBody {
  const lines = body.split("\n");
  const start = lines.findIndex((line, index) => {
    const trimmed = line.trim();
    if (QUOTE_START.test(trimmed)) return true;
    return (
      index > 0 && HEADER_END.test(trimmed) && WRAPPED_HEADER_START.test(lines[index - 1].trim())
    );
  });
  if (start === -1) return { own: body, quoted: "" };
  // The two-line header starts on the line before "wrote:".
  const cut = QUOTE_START.test(lines[start].trim()) ? start : start - 1;
  const own = lines.slice(0, cut).join("\n").trimEnd();
  if (own.trim() === "") return { own: body, quoted: "" };
  return { own, quoted: lines.slice(cut).join("\n").trim() };
}
