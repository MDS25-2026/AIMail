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

/** The reader's first name, the value behind [PERSON_1] in every demo email. */
export const DEMO_OWNER_NAME = "Aina";

/** The email whose reply has had no answer for a week: the To-do's Waiting list. */
export const DEMO_WAITING_EMAIL_ID = "demo-pallets";

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
      // Its trigger word "invois" matches the Malay payment template (data/templates.ts).
      suggestedTemplateId: "demo-template-bayaran",
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

    demoEmail({
      id: "demo-ceo-transfer",
      threadId: "demo-thread-ceo-transfer",
      // A look-alike domain: seribayu-group.example, not seribayu.example. Its checks failed, so
      // nothing is drafted until the reader confirms the sender (DEMO_CONFIRMED_DRAFTS).
      sender: "Hamid Yusof (CEO) <ceo@seribayu-group.example>",
      subject: "Urgent: transfer needed before 4pm, keep this confidential",
      body: [
        "[PERSON_1],",
        "",
        "I'm in a meeting with the bank and can't take calls. Please transfer RM 48,500 today to the account below for the Johor warehouse deposit. It must reach them before 4pm or we lose the unit.",
        "",
        "Account: [ACCOUNT_1]",
        "",
        "Keep this between us until it's done. I'll explain tomorrow.",
        "",
        "[PERSON_2]",
      ].join("\n"),
      timestamp: ago(50).toISOString(),
      priority: "critical",
      category: "security",
      categoryConfidence: 0.86,
      authStatus: AuthStatus.SpoofDetected,
      aiSummary:
        "Asks for an urgent RM 48,500 transfer to a new account before 4pm, and asks you to keep it secret. The sender's address failed its checks and is not the company's own domain: a common payment scam.",
      actionItems: [
        "Don't transfer anything; call the CEO's office on a number you already know",
        "Report the email to IT",
      ],
      draftReply: "",
      criticConfidence: 0,
      sources: [
        {
          label: "Payment procedure",
          excerpt:
            "New beneficiary accounts are confirmed by a phone call to a known number before any transfer. Urgency or secrecy in a payment request is a warning sign.",
          score: 0.88,
        },
      ],
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "Hamid Yusof" },
        { kind: "ACCOUNT", placeholder: "[ACCOUNT_1]", value: "5640 0011 2233" },
      ],
      egress: egress(ago(49), { PERSON: 2, ACCOUNT: 1 }, 380).slice(0, 3),
    }),

    demoEmail({
      id: "demo-quote",
      threadId: "demo-thread-quote",
      sender: "黄丽娟 <lijuan.huang@penangfresh.example>",
      subject: "Re: 冷链运输报价（槟城至新山）",
      body: [
        "[PERSON_1] 你好，",
        "",
        "谢谢你的回复。我们每周大约需要运送12个托盘，温度要求2至4°C，希望从11月第一周开始。",
        "",
        "请问报价能在本周五前发给我们吗？另外，如果签一年合约，是否有折扣？",
        "",
        "[PERSON_2]",
        "槟城鲜品有限公司",
      ].join("\n"),
      timestamp: ago(90).toISOString(),
      priority: "high",
      category: "client",
      categoryConfidence: 0.9,
      threadContext: [
        {
          sender: "黄丽娟 <lijuan.huang@penangfresh.example>",
          body: "你好，我们想了解从槟城到新山的每周冷链运输服务，请问可以提供报价吗？",
          snippet: "我们想了解从槟城到新山的每周冷链运输服务，请问可以提供报价吗？",
          isOwnReply: false,
          timestamp: ago(3 * 24 * 60).toISOString(),
        },
        {
          sender: `Aina <${DEMO_ACCOUNT}>`,
          body: "谢谢你的询问。为了准确报价，请告诉我每周的托盘数量、温度要求和开始日期。",
          snippet: "为了准确报价，请告诉我每周的托盘数量、温度要求和开始日期。",
          isOwnReply: true,
          timestamp: ago(2 * 24 * 60).toISOString(),
        },
      ],
      aiSummary:
        "[PERSON_2] confirms about 12 pallets a week at 2 to 4°C, starting the first week of November. Asks for the quote by Friday, and whether a one-year contract gets a discount.",
      actionItems: [
        "Send the quote before Friday",
        "Ask the sales manager about a one-year contract discount",
      ],
      draftReply: [
        "[PERSON_2] 你好，",
        "",
        "谢谢你提供的资料。每周12个托盘、2至4°C、11月第一周开始，这些我们都可以安排。正式报价我会在本周五前发给你。",
        "",
        "关于一年合约的折扣，我需要先和销售经理确认，会在报价中一并说明。",
        "",
        "祝好！",
        "[PERSON_1]",
      ].join("\n"),
      criticConfidence: 0.93,
      sources: [
        {
          label: "Refrigerated transport rate card",
          excerpt:
            "Contract discounts are approved by the sales manager. Do not promise a discount before it is approved.",
          score: 0.8,
        },
      ],
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "黄丽娟" },
      ],
      egress: egress(ago(89), { PERSON: 2 }, 290),
    }),

    demoEmail({
      id: "demo-payslip",
      threadId: "demo-thread-payslip",
      sender: "Seri Bayu Payroll <no-reply@payroll.seribayu.example>",
      subject: "Your September payslip is ready",
      body: [
        "Your payslip for September 2026 is now available in the HR portal.",
        "",
        "This is an automated message. Please do not reply.",
      ].join("\n"),
      timestamp: ago(8 * 60).toISOString(),
      priority: "low",
      category: "admin",
      categoryConfidence: 0.92,
      isAutomated: true,
      aiSummary: "Your September 2026 payslip is in the HR portal. Automated; no reply needed.",
      draftReply: "",
      criticConfidence: 0,
      piiMasked: false,
      egress: egress(ago(8 * 60 - 1), {}, 120).slice(0, 2),
    }),

    demoEmail({
      id: "demo-kenduri",
      threadId: "demo-thread-kenduri",
      sender: "Farah <farah.aziz@mel.example>",
      subject: "Jemputan kenduri kahwin adik saya, 25 Oktober",
      body: [
        "Salam [PERSON_1],",
        "",
        "Saya nak jemput awak ke majlis perkahwinan adik saya, [PERSON_2], pada hari Sabtu, 25 Oktober, dari 12 tengah hari hingga 4 petang di [LOCATION_1].",
        "",
        "Kalau boleh, beritahu saya sebelum 20 Oktober berapa orang yang akan datang ya, sebab kami nak sahkan jumlah katering.",
        "",
        "Terima kasih!",
        "[PERSON_3]",
      ].join("\n"),
      timestamp: ago(2 * 24 * 60).toISOString(),
      priority: "low",
      category: "personal",
      categoryConfidence: 0.94,
      isRead: true,
      tone: "casual",
      aiSummary:
        "[PERSON_3] invites you to [PERSON_2]'s wedding on Saturday 25 October, 12pm to 4pm, at [LOCATION_1]. Asks how many people are coming by 20 October, for the catering.",
      actionItems: ["Tell [PERSON_3] how many people are coming, before 20 October"],
      draftReply: [
        "Salam [PERSON_3],",
        "",
        "Terima kasih atas jemputan! Insya-Allah saya akan datang pada 25 Oktober. Saya akan beritahu berapa orang yang akan datang sebelum 20 Oktober.",
        "",
        "Tahniah kepada [PERSON_2] sekeluarga!",
        "",
        "[PERSON_1]",
      ].join("\n"),
      criticConfidence: 0.95,
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "Hafiz" },
        { kind: "PERSON", placeholder: "[PERSON_3]", value: "Farah" },
        { kind: "LOCATION", placeholder: "[LOCATION_1]", value: "Dewan Seri Melati, Shah Alam" },
      ],
      egress: egress(ago(2 * 24 * 60 - 1), { PERSON: 3, LOCATION: 1 }, 430),
    }),

    demoEmail({
      // Answered a week ago with a question and still unanswered: the To-do's Waiting list.
      id: DEMO_WAITING_EMAIL_ID,
      threadId: "demo-thread-pallets",
      sender: "Ravi Kumar <ravi@kotakjaya.example>",
      subject: "Pallet deliveries move to Tuesdays and Thursdays from November",
      body: [
        "Hi [PERSON_1],",
        "",
        "Because of a change at our depot, we're moving your pallet deliveries to Tuesdays and Thursdays from November.",
        "",
        "Please let me know if that works for your warehouse.",
        "",
        "Regards,",
        "[PERSON_2]",
        "Kotak Jaya Supplies",
      ].join("\n"),
      timestamp: ago(8 * 24 * 60).toISOString(),
      priority: "medium",
      category: "vendor",
      categoryConfidence: 0.89,
      isRead: true,
      isAnswered: true,
      sentAt: ago(7 * 24 * 60).toISOString(),
      aiSummary:
        "Kotak Jaya moves pallet deliveries to Tuesdays and Thursdays from November, and asks whether that works for your warehouse.",
      actionItems: ["Confirm whether Tuesday and Thursday deliveries suit the warehouse"],
      draftReply: [
        "Hi [PERSON_2],",
        "",
        "Thanks for letting us know. Tuesdays and Thursdays work for us, but our loading bay is busy before 10am. Could your drivers arrive between 10am and 3pm on those days?",
        "",
        "Best regards,",
        "[PERSON_1]",
      ].join("\n"),
      criticConfidence: 0.93,
      details: [
        { kind: "PERSON", placeholder: "[PERSON_1]", value: "Aina" },
        { kind: "PERSON", placeholder: "[PERSON_2]", value: "Ravi Kumar" },
      ],
      egress: egress(ago(8 * 24 * 60 - 1), { PERSON: 2 }, 300),
    }),
  ];
}
