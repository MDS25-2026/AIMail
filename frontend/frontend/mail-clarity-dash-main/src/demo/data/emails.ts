import {
  AuthStatus,
  MaskingStatus,
  ReviewCode,
  type Email,
  type EgressRecord,
} from "../../types/email";

/**
 * The demo mailbox. Everyone and every company here is made up; the reader is Aina, an operations
 * coordinator at Seri Bayu Logistics. Bodies and drafts carry placeholders, as the real masking
 * leaves them, and `details` holds the (equally made-up) values behind them.
 */

export const DEMO_ACCOUNT = "aina@seribayu.example";

const MINUTE = 60_000;

/** What the AI saw for one email: each step went to Gemini with the same details hidden. */
function egress(at: Date, hidden: Record<string, number>, chars: number): EgressRecord[] {
  const caught = Object.values(hidden).reduce((sum, count) => sum + count, 0);
  return ["route", "summary", "actions", "draft", "critic"].map((purpose) => ({
    at: at.toISOString(),
    caught,
    chars,
    hidden,
    provider: "gemini",
    purpose,
  }));
}

/** Fields every demo email shares; each email below sets what it is about. */
function demoEmail(email: Partial<Email> & Pick<Email, "id" | "subject" | "body">): Email {
  return {
    sender: "",
    preview: email.body.replace(/\s+/g, " ").slice(0, 140),
    timestamp: "",
    priority: "medium",
    threadContext: [],
    aiSummary: "",
    actionItems: [],
    draftReply: "",
    tone: "professional",
    isAutomated: false,
    hasUnreadAttachment: false,
    isAnswered: false,
    sources: [],
    piiMasked: true,
    criticConfidence: 0.95,
    masking: MaskingStatus.Complete,
    authStatus: AuthStatus.Pass,
    quantities: [],
    isRead: false,
    isDrafting: false,
    category: "internal",
    categoryConfidence: 0.9,
    details: [],
    egress: [],
    ...email,
  };
}

/** The mailbox as it starts, with times counted back from `now` so it always looks fresh. */
export function demoEmails(now: Date): Email[] {
  const ago = (minutes: number) => new Date(now.getTime() - minutes * MINUTE);

  return [
    demoEmail({
      id: "demo-port-klang",
      threadId: "demo-thread-port-klang",
      sender: "Daniel Lim <daniel.lim@harbourline.example>",
      subject: "Container held at Westport: corrected K1 needed by 3pm",
      body: [
        "Hi [PERSON_1],",
        "",
        "Customs have held container HLX-4471 at Westport because the K1 form and the commercial invoice don't match on the declared weight (4,200 kg on the invoice, 4,020 kg on the K1).",
        "",
        "They need a corrected K1 before 3pm today, or the container misses tomorrow's vessel and storage charges of RM 350 a day start.",
        "",
        "Can you send the corrected form, or tell me who on your side can sign it? You can reach me on [PHONE_1].",
        "",
        "Thanks,",
        "[PERSON_2]",
        "Harbourline Freight",
      ].join("\n"),
      timestamp: ago(25).toISOString(),
      priority: "critical",
      category: "client",
      categoryConfidence: 0.93,
      threadContext: [
        {
          sender: "Daniel Lim <daniel.lim@harbourline.example>",
          body: "Container HLX-4471 has arrived at Westport and is waiting for customs inspection. I'll update you once it clears.",
          snippet:
            "Container HLX-4471 has arrived at Westport and is waiting for customs inspection.",
          isOwnReply: false,
          timestamp: ago(26 * 60).toISOString(),
        },
      ],
      aiSummary:
        "Customs are holding container HLX-4471 at Westport because the K1 form and the invoice give different weights. A corrected K1 is needed before 3pm today, or the container misses tomorrow's vessel and storage costs RM 350 a day.",
      actionItems: [
        "Send a corrected K1 with the invoice weight (4,200 kg) before 3pm today",
        "Confirm who on your side signs the corrected K1",
      ],
      draftReply: [
        "Hi [PERSON_2],",
        "",
        "Thank you for the quick warning. The commercial invoice is correct at 4,200 kg; the K1 was typed from an earlier packing list. I'm preparing a corrected K1 now and will send it to you before 2pm, signed by our licensed customs officer.",
        "",
        "If customs need anything else to release HLX-4471 today, please call me straight away.",
        "",
        "Best regards,",
        "[PERSON_1]",
      ].join("\n"),
      criticConfidence: 0.94,
      sources: [
        {
          label: "Customs clearance checklist",
          excerpt:
            "Where the K1 and the commercial invoice disagree, the invoice weight stands; the K1 must be reissued and signed by the licensed customs officer.",
          score: 0.82,
        },
      ],
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "Daniel Lim" },
        { kind: "PHONE", placeholder: "[PHONE_1]", value: "012-000 4471" },
      ],
      egress: egress(ago(24), { PERSON: 2, PHONE: 1 }, 610),
    }),

    demoEmail({
      id: "demo-invois",
      threadId: "demo-thread-invois",
      sender: "Nur Izzati <izzati@sinarpack.example>",
      subject: "Peringatan: invois SP-2291 telah melepasi tarikh akhir",
      body: [
        "Assalamualaikum [PERSON_1],",
        "",
        "Untuk makluman, invois SP-2291 bernilai RM 12,480.00 bagi bekalan kotak beralun bulan September telah melepasi tarikh akhir bayaran pada 30 September.",
        "",
        "Mohon pihak puan semak status bayaran dan maklumkan tarikh jangkaan bayaran. Jika bayaran telah dibuat, sila kongsikan slip pindahan supaya kami boleh mengemas kini rekod.",
        "",
        "Sekian, terima kasih.",
        "",
        "[PERSON_2]",
        "Jabatan Akaun, Sinar Pack Sdn Bhd",
      ].join("\n"),
      timestamp: ago(3 * 60).toISOString(),
      priority: "high",
      category: "vendor",
      categoryConfidence: 0.91,
      aiSummary:
        "Sinar Pack says invoice SP-2291 (RM 12,480.00, September carton supply) passed its 30 September due date. They ask for the payment status and an expected payment date, or the transfer slip if it is already paid.",
      actionItems: [
        "Check the payment status of invoice SP-2291 with Finance",
        "Reply with the expected payment date, or the transfer slip if paid",
      ],
      draftReply: [
        "Waalaikumussalam [PERSON_2],",
        "",
        "Terima kasih atas peringatan ini. Kami sedang menyemak status bayaran invois SP-2291 dengan bahagian kewangan dan akan memaklumkan tarikh jangkaan bayaran selewat-lewatnya esok.",
        "",
        "Jika bayaran telah dibuat, kami akan kongsikan slip pindahan bersama maklum balas tersebut.",
        "",
        "Sekian, terima kasih.",
        "",
        "[PERSON_1]",
      ].join("\n"),
      criticConfidence: 0.92,
      sources: [
        {
          label: "Accounts payable procedure",
          excerpt:
            "Answer supplier payment queries within one working day. Confirm the status with Finance before giving a payment date.",
          score: 0.77,
        },
      ],
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "Nur Izzati" },
      ],
      egress: egress(ago(3 * 60 - 1), { PERSON: 2 }, 540),
    }),

    demoEmail({
      id: "demo-meeting",
      threadId: "demo-thread-meeting",
      sender: "陈伟明 <weiming.chen@seribayu.example>",
      subject: "下周三部门会议改期",
      body: [
        "[PERSON_1] 你好，",
        "",
        "原定下周三上午10点的仓储部门会议，因为要配合盘点工作，改到下周四下午2点半，地点不变，仍在三楼会议室。",
        "",
        "请确认你能否出席，并在周二前把九月份的出货报告发给我，方便会上讨论。",
        "",
        "谢谢！",
        "[PERSON_2]",
      ].join("\n"),
      timestamp: ago(5 * 60).toISOString(),
      priority: "medium",
      category: "internal",
      categoryConfidence: 0.95,
      isRead: true,
      aiSummary:
        "The warehouse team meeting moves from next Wednesday 10am to next Thursday 2:30pm because of stock-taking, in the same third-floor room. Asks whether you can attend, and for the September shipment report by Tuesday.",
      actionItems: [
        "Confirm you can attend on Thursday at 2:30pm",
        "Send the September shipment report before Tuesday",
      ],
      draftReply: [
        "[PERSON_2] 你好，",
        "",
        "收到，谢谢通知。我可以出席下周四下午2点半的会议。九月份的出货报告我会在周二前发给你。",
        "",
        "谢谢！",
        "[PERSON_1]",
      ].join("\n"),
      criticConfidence: 0.96,
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "陈伟明" },
      ],
      egress: egress(ago(5 * 60 - 1), { PERSON: 2 }, 320),
    }),

    demoEmail({
      id: "demo-leave-plan",
      threadId: "demo-thread-leave-plan",
      sender: "HR Team <hr@seribayu.example>",
      subject: "Reminder: submit your 2027 leave plan by 31 October",
      body: [
        "Dear [PERSON_1],",
        "",
        "This is a reminder to submit your annual leave plan for 2027 in the HR portal by 31 October. Planned leave helps us arrange cover during the peak season in December and January.",
        "",
        "Up to 5 days of unused 2026 leave can be carried forward; anything above that lapses on 31 December.",
        "",
        "Regards,",
        "HR Team",
      ].join("\n"),
      timestamp: ago(26 * 60).toISOString(),
      priority: "low",
      category: "admin",
      categoryConfidence: 0.88,
      isRead: true,
      aiSummary:
        "HR asks for your 2027 leave plan in the HR portal by 31 October. Up to 5 unused 2026 leave days carry forward; the rest lapse on 31 December.",
      actionItems: ["Submit the 2027 leave plan in the HR portal by 31 October"],
      draftReply: [
        "Dear HR Team,",
        "",
        "Thank you for the reminder. I will submit my 2027 leave plan in the HR portal before 31 October.",
        "",
        "Could you confirm whether the carried-forward days must be used by a particular date in 2027?",
        "",
        "Regards,",
        "[PERSON_1]",
      ].join("\n"),
      // Below the 0.9 threshold: the policy says nothing about when carried days expire, so the
      // checker asks a person to look before this goes out.
      criticConfidence: 0.84,
      reviewReasons: [{ code: ReviewCode.LowConfidence }],
      sources: [
        {
          label: "Leave policy",
          excerpt:
            "Up to five days of unused annual leave may be carried forward to the following year.",
          score: 0.71,
        },
      ],
      details: [{ kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" }],
      egress: egress(ago(26 * 60 - 1), { PERSON: 1 }, 410),
    }),
  ];
}
