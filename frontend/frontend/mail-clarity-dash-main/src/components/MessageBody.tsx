import { useRenderedBody } from "../lib/useRenderedBody";
import WithDetails from "./WithDetails";

// contain:paint makes this the containing block even for position:fixed, and clips to it:
// sanitised email HTML keeps inline styles, and a fixed element must not draw over the dashboard.
export const HTML_BODY_CLASS =
  "relative max-w-none overflow-x-auto text-sm text-fg-body [contain:paint] [&_a]:text-brand [&_a]:underline [&_img]:max-w-full";

/** One message's body, as safe as the open email's; remote images stay blocked. */
export default function MessageBody({ body }: { body: string }) {
  const rendered = useRenderedBody(body, false);
  if (rendered.html === null) {
    return (
      <p className="whitespace-pre-wrap text-sm text-fg-body">
        <WithDetails text={body} />
      </p>
    );
  }
  return <div className={HTML_BODY_CLASS} dangerouslySetInnerHTML={{ __html: rendered.html }} />;
}
