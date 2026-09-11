import type { Email } from "../types/email";

/**
 * Single source of truth the Dashboard reads from. Swapping this for a real
 * API call later should be a one-line change in the top-level component.
 */
export const mockEmails: Email[] = [
  {
    id: "eml_001",
    originalBody:
      "Hi Alex,\n\nGood news — legal signed off on the redlines this morning, so we're clear on all the outstanding terms.\n\nThe last thing we need is written confirmation of the final seat count. Our records show 120, but I want to be sure before we countersign. If you can confirm by Friday we'll have the executed MSA back to you the same day.\n\nThanks,\nDana Whitfield\nWhitfield Corp",
    sender: "Dana Whitfield",
    subject: "Q3 renewal terms — need confirmation by Friday",
    preview:
      "Legal signed off on the redlines. We just need your confirmation on the seat count before we countersign.",
    timestamp: "2026-07-31T09:14:00Z",
    priority: "high",
    threadContext: [
      { sender: "Dana Whitfield", snippet: "Attaching the redlined MSA for your review." },
      { sender: "You", snippet: "Thanks — routing to legal today, will revert by Wednesday." },
      { sender: "Dana Whitfield", snippet: "Legal signed off. Confirm seat count by Friday?" },
    ],
    aiSummary:
      "Dana needs written confirmation of the final seat count (currently 120) so their legal team can countersign the Q3 renewal before Friday.",
    actionItems: [
      "Confirm final seat count with Finance",
      "Reply to Dana with the confirmed number",
      "Forward the countersigned MSA to procurement",
    ],
    draftReply:
      "Hi Dana,\n\nThanks for pushing this through legal. I can confirm we're moving forward with 120 seats for the Q3 renewal. Please go ahead and countersign — I'll forward the executed copy to procurement once it's back.\n\nBest,\nAlex",
    tone: "professional",
    sources: [
      { label: "Past emails (8)" },
      { label: "MSA_redline_v4.pdf" },
      { label: "CRM: Whitfield Corp" },
    ],
    piiMasked: true,
    criticConfidence: 0.92,
  },
  {
    id: "eml_002",
    originalBody:
      "Morning all,\n\nStandup notes are in the doc, but flagging one blocker here: staging is still pinned to build 412 and we expected 418. Marco spotted a failed migration in the deploy log.\n\nCan someone with deploy access take a look this morning? QA can't start the regression pass until staging is current.\n\nThanks,\nPriya",
    sender: "Priya Raman",
    subject: "Standup notes + blocked on staging deploy",
    preview:
      "Staging is still pinned to last week's build. Can someone with deploy access take a look this morning?",
    timestamp: "2026-07-31T08:47:00Z",
    priority: "medium",
    threadContext: [
      { sender: "Priya Raman", snippet: "Staging pinned to build 412, expected 418." },
      { sender: "Marco Silva", snippet: "I see a failed migration in the deploy log." },
    ],
    aiSummary:
      "Priya is blocked because staging is running an outdated build; a failed migration appears to be the cause and someone with deploy access needs to re-run it.",
    actionItems: [
      "Re-run the failed migration on staging",
      "Reply to Priya once staging is on build 418",
    ],
    draftReply:
      "Hey Priya,\n\nGood catch — looks like the migration failed on the 418 deploy. I'll re-run it this morning and ping the channel once staging is current.\n\nThanks,\nAlex",
    tone: "casual",
    sources: [{ label: "Past emails (3)" }, { label: "Deploy log #418" }],
    piiMasked: false,
    criticConfidence: 0.83,
  },
  {
    id: "eml_003",
    originalBody:
      "Hello,\n\nI'm Marcus from the Northwind security team. We're kicking off vendor review for the pilot next week.\n\nTo get started we'll need your current SOC 2 Type II report plus answers to the attached security questionnaire. Turnaround before Wednesday would keep us on schedule.\n\nBest regards,\nMarcus Oyelaran\nNorthwind Information Security",
    sender: "Marcus Oyelaran",
    subject: "Intro: security questionnaire for the Northwind pilot",
    preview:
      "We're kicking off vendor review next week and need your SOC 2 report plus answers to the attached questionnaire.",
    timestamp: "2026-07-31T07:20:00Z",
    priority: "high",
    threadContext: [],
    aiSummary:
      "A first-contact request from Northwind's security team asking for the SOC 2 Type II report and a completed vendor questionnaire before their pilot review next week.",
    actionItems: [
      "Send the current SOC 2 Type II report",
      "Route the questionnaire to Security for completion",
    ],
    draftReply:
      "Hi Marcus,\n\nThanks for reaching out. I'm attaching our current SOC 2 Type II report and have routed the questionnaire to our security team — you should have completed answers by Wednesday.\n\nBest,\nAlex",
    tone: "professional",
    sources: [{ label: "SOC2_TypeII_2026.pdf" }],
    piiMasked: true,
    criticConfidence: 0.71,
  },
  {
    id: "eml_004",
    originalBody:
      "Hi,\n\nFriendly reminder that we still need your speaker materials for the printed program: a 100-word bio and a high-resolution headshot.\n\nThe deadline is the end of the month — after that we lock the program with the printer.\n\nThanks!\nConference Ops",
    sender: "Conference Ops",
    subject: "Your speaker bio is due",
    preview: "We still need a 100-word bio and a headshot for the program. Deadline is end of month.",
    timestamp: "2026-07-30T16:05:00Z",
    priority: "low",
    threadContext: [
      { sender: "Conference Ops", snippet: "Reminder: speaker materials due end of month." },
    ],
    aiSummary:
      "Conference organizers need a 100-word speaker bio and a headshot before the end of the month for the printed program.",
    actionItems: ["Send an updated 100-word bio", "Attach a current headshot"],
    draftReply:
      "Hi there,\n\nThanks for the reminder. I'll send over my bio and headshot before the end of the month.\n\nBest,\nAlex",
    tone: "professional",
    sources: [{ label: "Speaker packet.pdf" }],
    piiMasked: true,
    criticConfidence: 0.64,
  },
  {
    id: "eml_005",
    originalBody:
      "Hey Alex!\n\nI land Monday night and I'm staying at the same hotel. Want to grab coffee Tuesday morning before things kick off? Anytime before 9 works for me — the lobby cafe opens at 7.\n\nLet me know,\nJen",
    sender: "Jen Alvarez",
    subject: "Coffee before the offsite?",
    preview: "I land Monday night — want to grab coffee Tuesday morning before things kick off?",
    timestamp: "2026-07-30T11:32:00Z",
    priority: "low",
    threadContext: [
      { sender: "Jen Alvarez", snippet: "Booked my flights for the offsite." },
      { sender: "You", snippet: "Nice — I'm in Monday evening too." },
    ],
    aiSummary:
      "Jen is proposing coffee on Tuesday morning before the offsite starts and is waiting on a yes/no plus a time.",
    actionItems: ["Confirm Tuesday 8:30am coffee with Jen"],
    draftReply:
      "Hey Jen,\n\nYes please — 8:30 in the hotel lobby works for me. See you Tuesday!\n\nAlex",
    tone: "casual",
    sources: [{ label: "Past emails (5)" }, { label: "Calendar: Offsite" }],
    piiMasked: false,
    criticConfidence: 0.88,
  },
];
