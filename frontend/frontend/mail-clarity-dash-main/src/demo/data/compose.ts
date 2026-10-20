import { ComposeState, type ComposeDraft } from "../../types/compose";
import type { Detail, Source } from "../../types/email";
import { DEMO_DOCUMENTS } from "./documents";
import { DEMO_OWNER_NAME } from "./emails";

/**
 * Compose in the demo: one draft waiting to be written, one sent yesterday, and the AI's answers
 * written in advance. Text keeps its placeholders, as the backend stores it; `details` fills them in.
 */

const MINUTE = 60_000;
const text = (...lines: string[]) => lines.join("\n");

/** The reader's name signs every email, as [PERSON_1] does in the demo mailbox. */
export const DEMO_COMPOSE_DETAILS: Detail[] = [
  { kind: "PERSON", placeholder: "[PERSON_1]", value: DEMO_OWNER_NAME },
  { kind: "PHONE", placeholder: "[PHONE_1]", value: "012-000 3108" },
];

/** A chunk of a demo document as a draft cites it, so every excerpt is the document's own words. */
function sourceFrom(documentId: string, chunk: number, score: number): Source {
  const document = DEMO_DOCUMENTS.find((candidate) => candidate.document_id === documentId);
  const part = document?.chunks[chunk];
  return { label: document?.title ?? "", excerpt: part?.content ?? "", score, chunkId: part?.id };
}

export const DEMO_COMPOSE_SOURCES: Source[] = [
  sourceFrom("demo-doc-leave", 0, 0.86),
  sourceFrom("demo-doc-leave", 1, 0.79),
];

const SIGN_OFF = ["", "Best regards,", "[PERSON_1]"];

/** What "Write with AIMail" answers in the demo, whatever the brief says. */
export const DEMO_COMPOSE_WRITTEN = {
  subject: "Please plan next year's annual leave by 31 October",
  body: text(
    "Hi team,",
    "",
    "A reminder to plan your annual leave for next year in the HR portal by 31 October, so we can arrange cover for the December and January peak.",
    "",
    "Up to five days of unused annual leave can be carried forward to next year. Any days above that lapse on 31 December, so please book them before then.",
    "",
    "If anything is unclear, call me on [PHONE_1].",
    ...SIGN_OFF,
  ),
};

/** Refine with the suggestions under the box; anything typed is not prepared in the demo. */
export const DEMO_COMPOSE_REFINED = {
  direct: text(
    "Hi team,",
    "",
    "Please put next year's annual leave in the HR portal by 31 October. You can carry forward up to five unused days; the rest lapse on 31 December.",
    "",
    "Questions? Call me on [PHONE_1].",
    ...SIGN_OFF,
  ),
  deadline: text(
    "Hi team,",
    "",
    "Please plan your annual leave for next year in the HR portal by Friday, 31 October, so we can arrange cover for the December and January peak.",
    "",
    "Up to five days of unused annual leave can be carried forward. Any days above that lapse on 31 December, so please book them before then.",
    "",
    "If anything is unclear, call me on [PHONE_1] before the deadline.",
    ...SIGN_OFF,
  ),
};

function demoDraft(draft: Partial<ComposeDraft> & Pick<ComposeDraft, "id" | "updatedAt">) {
  return {
    to: [],
    cc: [],
    subject: "",
    brief: "",
    body: "",
    tone: "professional",
    state: ComposeState.Draft,
    sources: [],
    reviewReasons: [],
    details: DEMO_COMPOSE_DETAILS,
    egress: [],
    ...draft,
  } satisfies ComposeDraft;
}

/** Compose as it starts, with times counted back from `now`. */
export function demoComposeDrafts(now: Date): ComposeDraft[] {
  const ago = (minutes: number) => new Date(now.getTime() - minutes * MINUTE).toISOString();
  return [
    demoDraft({
      id: "demo-compose-leave",
      to: ["Operations team <ops@seribayu.example>"],
      brief:
        "Remind the team to plan next year's leave in the HR portal by 31 October, and mention the carry-forward rule. They can call me on [PHONE_1].",
      updatedAt: ago(40),
    }),
    demoDraft({
      id: "demo-compose-payment",
      to: ["Finance <payments@seribayu.example>"],
      subject: "Proof of payment for Tasik Supplies",
      brief: "Ask Finance to send Tasik Supplies the transfer slip for last month's invoice.",
      body: text(
        "Hi Finance,",
        "",
        "Tasik Supplies have asked for proof of last month's payment. Could you send them the bank transfer slip from the payments mailbox?",
        "",
        "Thank you,",
        "[PERSON_1]",
      ),
      sources: [sourceFrom("demo-doc-payables", 1, 0.81)],
      criticConfidence: 0.94,
      state: ComposeState.Sent,
      generatedAt: ago(26 * 60 + 5),
      sentAt: ago(26 * 60),
      updatedAt: ago(26 * 60),
    }),
  ];
}
