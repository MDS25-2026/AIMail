import WithDetails from "./WithDetails";

// http(s) only; a closing bracket or sentence punctuation after the address is not part of it.
const URL_PATTERN = /https?:\/\/[^\s<>()"']*[^\s<>()"'.,;:!?]/g;

/** Text with its web addresses as links that open in a new tab; the address stays visible as written. */
export default function LinkedText({ text }: { text: string }) {
  const parts: { text: string; isLink: boolean }[] = [];
  let last = 0;
  for (const match of text.matchAll(URL_PATTERN)) {
    parts.push({ text: text.slice(last, match.index), isLink: false });
    parts.push({ text: match[0], isLink: true });
    last = match.index + match[0].length;
  }
  parts.push({ text: text.slice(last), isLink: false });
  return (
    <>
      {parts.map((part, index) =>
        part.isLink ? (
          <a
            key={index}
            href={part.text}
            target="_blank"
            rel="noopener noreferrer"
            className="break-all text-brand underline hover:text-brand-strong"
          >
            {part.text}
          </a>
        ) : (
          <WithDetails key={index} text={part.text} />
        ),
      )}
    </>
  );
}
