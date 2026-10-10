// The first signed-in Gmail account; a reader signed in to several may land in another one.
const GMAIL_THREAD = "https://mail.google.com/mail/u/0/#all/";

/** A Gmail thread by the hex id the API uses; Gmail still opens it from that form. */
export function gmailThreadUrl(threadId: string): string {
  return `${GMAIL_THREAD}${encodeURIComponent(threadId)}`;
}
