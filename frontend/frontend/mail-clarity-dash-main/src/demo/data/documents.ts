import type { DocumentDetail } from "../../types/knowledge";

/**
 * Seri Bayu Logistics' (made-up) company documents: the Knowledge page, and what the demo drafts
 * cite as sources. Each source excerpt in data/emails.ts appears word for word in one of these.
 */

type Section = { section: string; content: string };

function demoDocument(id: string, title: string, source: string, sections: Section[]) {
  const chunks = sections.map((part, index) => ({
    id: `${id}-chunk-${index}`,
    chunk_idx: index,
    section: part.section,
    content: part.content,
  }));
  return {
    document_id: id,
    title,
    source,
    doc_type: "policy",
    chunk_count: chunks.length,
    content: sections.map((part) => `${part.section}\n\n${part.content}`).join("\n\n"),
    chunks,
  } satisfies DocumentDetail;
}

export const DEMO_DOCUMENTS: readonly DocumentDetail[] = [
  demoDocument(
    "demo-doc-customs",
    "Customs clearance checklist",
    "customs-clearance-checklist.pdf",
    [
      {
        section: "1. Documents for every import",
        content:
          "Each container needs a commercial invoice, a packing list, a bill of lading and a customs declaration (K1). The declared weight and value must be the same on all four.",
      },
      {
        section: "2. When documents disagree",
        content:
          "Where the K1 and the commercial invoice disagree, the invoice weight stands; the K1 must be reissued and signed by the licensed customs officer.",
      },
      {
        section: "3. Deadlines",
        content:
          "Customs at Westport and Northport release containers for the next vessel only if corrected documents arrive by 3pm. Storage charges apply from the day after a missed release.",
      },
    ],
  ),
  demoDocument(
    "demo-doc-payables",
    "Accounts payable procedure",
    "accounts-payable-procedure.pdf",
    [
      {
        section: "1. Supplier queries",
        content:
          "Answer supplier payment queries within one working day. Confirm the status with Finance before giving a payment date.",
      },
      {
        section: "2. Proof of payment",
        content:
          "When a supplier asks for proof of a payment already made, Finance sends the bank transfer slip from the payments mailbox, never from a personal one.",
      },
    ],
  ),
  demoDocument("demo-doc-payments", "Payment procedure", "payment-procedure.pdf", [
    {
      section: "1. New beneficiary accounts",
      content:
        "New beneficiary accounts are confirmed by a phone call to a known number before any transfer. Urgency or secrecy in a payment request is a warning sign.",
    },
    {
      section: "2. Approval limits",
      content:
        "Transfers above RM 20,000 need two approvers from Finance. No single person, whatever their role, can approve one alone.",
    },
  ]),
  demoDocument("demo-doc-leave", "Leave policy", "leave-policy.pdf", [
    {
      section: "1. Annual leave",
      content:
        "Staff plan their annual leave for the coming year in the HR portal by 31 October, so cover can be arranged for the December and January peak.",
    },
    {
      section: "2. Carrying leave forward",
      content:
        "Up to five days of unused annual leave may be carried forward to the following year. Any days above that lapse on 31 December.",
    },
  ]),
  demoDocument("demo-doc-rates", "Refrigerated transport rate card", "cold-chain-rate-card.pdf", [
    {
      section: "1. Weekly contracts",
      content:
        "Weekly refrigerated runs between Penang and Johor Bahru are priced per pallet at 2 to 8°C. Quotes are valid for 30 days.",
    },
    {
      section: "2. Discounts",
      content:
        "Contract discounts are approved by the sales manager. Do not promise a discount before it is approved.",
    },
  ]),
];
