import type { Tone } from "../../types/email";
import type { Language } from "../../lib/preferences";

/**
 * The AI's answers in the demo, written in advance: no model is called (specs/features/demo-mailbox.md).
 * Like real drafts, they keep the placeholders; each email's `details` fills them in.
 */

export type PreparedAnswers = {
  /** The draft in the tone the email does not start in. */
  otherTone?: Partial<Record<Tone, string>>;
  /** Refine with the "Make it more direct" suggestion. */
  direct?: string;
  /** Refine with the "Add a deadline" suggestion. */
  deadline?: string;
  /** The email's body in the languages it is not written in. */
  translations: Partial<Record<Language, string>>;
};

const text = (...lines: string[]) => lines.join("\n");

export const DEMO_ANSWERS: Readonly<Record<string, PreparedAnswers>> = {
  "demo-port-klang": {
    otherTone: {
      casual: text(
        "Hi [PERSON_2],",
        "",
        "Thanks for the heads-up! The invoice is right at 4,200 kg; the K1 was typed from an old packing list. I'm fixing it now and will send you the signed K1 before 2pm.",
        "",
        "If customs need anything else for HLX-4471 today, just call me.",
        "",
        "Cheers,",
        "[PERSON_1]",
      ),
    },
    direct: text(
      "Hi [PERSON_2],",
      "",
      "The invoice weight of 4,200 kg is correct. You'll have a corrected K1, signed by our licensed customs officer, before 2pm.",
      "",
      "Call me if customs need anything else to release HLX-4471 today.",
      "",
      "Best regards,",
      "[PERSON_1]",
    ),
    deadline: text(
      "Hi [PERSON_2],",
      "",
      "Thank you for the quick warning. The commercial invoice is correct at 4,200 kg; the K1 was typed from an earlier packing list. You will have the corrected K1, signed by our licensed customs officer, by 2pm today, an hour before the 3pm customs cut-off.",
      "",
      "If customs need anything else to release HLX-4471 today, please call me straight away.",
      "",
      "Best regards,",
      "[PERSON_1]",
    ),
    translations: {
      ms: text(
        "Hai [PERSON_1],",
        "",
        "Kastam telah menahan kontena HLX-4471 di Westport kerana borang K1 dan invois komersial tidak sepadan pada berat yang diisytiharkan (4,200 kg pada invois, 4,020 kg pada K1).",
        "",
        "Mereka memerlukan K1 yang telah dibetulkan sebelum 3 petang hari ini. Jika tidak, kontena akan terlepas kapal esok dan caj penyimpanan RM 350 sehari akan bermula.",
        "",
        "Boleh hantar borang yang telah dibetulkan, atau beritahu saya siapa di pihak anda yang boleh menandatanganinya? Anda boleh hubungi saya di [PHONE_1].",
        "",
        "Terima kasih,",
        "[PERSON_2]",
        "Harbourline Freight",
      ),
      zh: text(
        "[PERSON_1] 你好，",
        "",
        "海关在 Westport 扣留了 HLX-4471 号集装箱，因为 K1 表格与商业发票上申报的重量不一致（发票为 4,200 公斤，K1 为 4,020 公斤）。",
        "",
        "他们需要在今天下午3点前收到更正后的 K1，否则集装箱将赶不上明天的船期，并开始产生每天 RM 350 的仓储费。",
        "",
        "你能发送更正后的表格吗？或者告诉我你们那边谁可以签署？你可以拨打 [PHONE_1] 联系我。",
        "",
        "谢谢，",
        "[PERSON_2]",
        "Harbourline Freight",
      ),
    },
  },

  "demo-invois": {
    otherTone: {
      casual: text(
        "Waalaikumussalam [PERSON_2],",
        "",
        "Terima kasih sebab ingatkan. Kami tengah semak status bayaran invois SP-2291 dengan bahagian kewangan, dan akan maklumkan tarikh bayaran paling lewat esok.",
        "",
        "Kalau dah bayar, kami akan kongsikan slip pindahan sekali.",
        "",
        "Terima kasih!",
        "",
        "[PERSON_1]",
      ),
    },
    direct: text(
      "Waalaikumussalam [PERSON_2],",
      "",
      "Kami sedang menyemak status bayaran invois SP-2291 dan akan memaklumkan tarikh jangkaan bayaran, atau menghantar slip pindahan, selewat-lewatnya esok.",
      "",
      "Terima kasih.",
      "",
      "[PERSON_1]",
    ),
    deadline: text(
      "Waalaikumussalam [PERSON_2],",
      "",
      "Terima kasih atas peringatan ini. Kami sedang menyemak status bayaran invois SP-2291 dengan bahagian kewangan dan akan memaklumkan tarikh jangkaan bayaran sebelum 5 petang esok.",
      "",
      "Jika bayaran telah dibuat, kami akan kongsikan slip pindahan bersama maklum balas tersebut.",
      "",
      "Sekian, terima kasih.",
      "",
      "[PERSON_1]",
    ),
    translations: {
      en: text(
        "Assalamualaikum [PERSON_1],",
        "",
        "For your information, invoice SP-2291 for RM 12,480.00, for the September supply of corrugated boxes, passed its payment due date of 30 September.",
        "",
        "Please check the payment status and let us know the expected payment date. If payment has been made, please share the transfer slip so we can update our records.",
        "",
        "Thank you.",
        "",
        "[PERSON_2]",
        "Accounts Department, Sinar Pack Sdn Bhd",
      ),
      zh: text(
        "[PERSON_1] 您好，",
        "",
        "特此通知，金额为 RM 12,480.00 的 SP-2291 号发票（九月份瓦楞纸箱供应）已超过 9 月 30 日的付款期限。",
        "",
        "请贵方查核付款状态，并告知预计付款日期。如已付款，请提供转账凭证，以便我们更新记录。",
        "",
        "谢谢。",
        "",
        "[PERSON_2]",
        "Sinar Pack Sdn Bhd 会计部",
      ),
    },
  },

  "demo-meeting": {
    otherTone: {
      casual: text(
        "[PERSON_2]，",
        "",
        "收到！周四下午2点半我可以来。九月份的出货报告周二前发给你。",
        "",
        "谢啦！",
        "[PERSON_1]",
      ),
    },
    direct: text(
      "[PERSON_2] 你好，",
      "",
      "我会出席下周四下午2点半的会议，九月份的出货报告周二前发给你。",
      "",
      "[PERSON_1]",
    ),
    deadline: text(
      "[PERSON_2] 你好，",
      "",
      "收到，谢谢通知。我可以出席下周四下午2点半的会议。九月份的出货报告我会在下周一下班前发给你，比周二的期限早一天。",
      "",
      "谢谢！",
      "[PERSON_1]",
    ),
    translations: {
      en: text(
        "Hi [PERSON_1],",
        "",
        "The warehouse team meeting planned for next Wednesday at 10am has moved to next Thursday at 2:30pm because of stock-taking. The place is the same: the third-floor meeting room.",
        "",
        "Please confirm whether you can attend, and send me the September shipment report before Tuesday so we can discuss it at the meeting.",
        "",
        "Thanks!",
        "[PERSON_2]",
      ),
      ms: text(
        "Hai [PERSON_1],",
        "",
        "Mesyuarat jabatan gudang yang dijadualkan pada hari Rabu depan jam 10 pagi telah dipindahkan ke hari Khamis depan jam 2:30 petang kerana kerja pengiraan stok. Tempatnya sama, di bilik mesyuarat tingkat tiga.",
        "",
        "Sila sahkan sama ada anda boleh hadir, dan hantar laporan penghantaran bulan September kepada saya sebelum hari Selasa untuk dibincangkan dalam mesyuarat.",
        "",
        "Terima kasih!",
        "[PERSON_2]",
      ),
    },
  },

  "demo-leave-plan": {
    otherTone: {
      casual: text(
        "Hi HR team,",
        "",
        "Thanks for the reminder! I'll get my 2027 leave plan into the HR portal before 31 October.",
        "",
        "Quick question: do the carried-forward days need to be used by a certain date in 2027?",
        "",
        "Thanks,",
        "[PERSON_1]",
      ),
    },
    direct: text(
      "Dear HR Team,",
      "",
      "I will submit my 2027 leave plan in the HR portal before 31 October. Must the carried-forward days be used by a particular date in 2027?",
      "",
      "Regards,",
      "[PERSON_1]",
    ),
    deadline: text(
      "Dear HR Team,",
      "",
      "Thank you for the reminder. I will submit my 2027 leave plan in the HR portal by 24 October, a week before the deadline.",
      "",
      "Could you confirm whether the carried-forward days must be used by a particular date in 2027?",
      "",
      "Regards,",
      "[PERSON_1]",
    ),
    translations: {
      ms: text(
        "[PERSON_1] yang dihormati,",
        "",
        "Ini adalah peringatan untuk menghantar pelan cuti tahunan 2027 anda di portal HR sebelum 31 Oktober. Cuti yang dirancang membantu kami mengatur pengganti semasa musim puncak pada bulan Disember dan Januari.",
        "",
        "Sehingga 5 hari cuti 2026 yang tidak digunakan boleh dibawa ke tahun hadapan; selebihnya akan luput pada 31 Disember.",
        "",
        "Sekian,",
        "Pasukan HR",
      ),
      zh: text(
        "[PERSON_1] 您好：",
        "",
        "提醒您在 10 月 31 日前于 HR 系统中提交 2027 年的年假计划。提前规划休假有助于我们在 12 月和 1 月的旺季安排人手。",
        "",
        "2026 年未使用的年假最多可结转 5 天，超出部分将于 12 月 31 日失效。",
        "",
        "此致",
        "HR 团队",
      ),
    },
  },

  "demo-ceo-transfer": {
    translations: {
      ms: text(
        "[PERSON_1],",
        "",
        "Saya sedang bermesyuarat dengan pihak bank dan tidak boleh menjawab panggilan. Sila pindahkan RM 48,500 hari ini ke akaun di bawah untuk deposit gudang Johor. Wang itu mesti sampai sebelum 4 petang atau kita akan kehilangan unit itu.",
        "",
        "Akaun: [ACCOUNT_1]",
        "",
        "Rahsiakan perkara ini sehingga selesai. Saya akan terangkan esok.",
        "",
        "[PERSON_2]",
      ),
      zh: text(
        "[PERSON_1]，",
        "",
        "我正在和银行开会，无法接电话。请今天把 RM 48,500 转到下面的账户，作为柔佛仓库的订金。款项必须在下午4点前到账，否则我们会失去这个单位。",
        "",
        "账户：[ACCOUNT_1]",
        "",
        "事情办完之前请保密，我明天再解释。",
        "",
        "[PERSON_2]",
      ),
    },
  },

  "demo-quote": {
    otherTone: {
      casual: text(
        "[PERSON_2] 你好，",
        "",
        "谢谢你的资料！每周12个托盘、2至4°C、11月第一周开始，我们都没问题。报价周五前发给你。",
        "",
        "一年合约的折扣我先问问销售经理，到时在报价里告诉你。",
        "",
        "祝好！",
        "[PERSON_1]",
      ),
    },
    direct: text(
      "[PERSON_2] 你好，",
      "",
      "每周12个托盘、2至4°C、11月第一周开始，我们可以安排。报价将在本周五前发出；一年合约的折扣需经销售经理确认，会在报价中说明。",
      "",
      "[PERSON_1]",
    ),
    deadline: text(
      "[PERSON_2] 你好，",
      "",
      "谢谢你提供的资料。每周12个托盘、2至4°C、11月第一周开始，这些我们都可以安排。正式报价我会在本周四下班前发给你，比你要求的周五早一天。",
      "",
      "关于一年合约的折扣，我需要先和销售经理确认，会在报价中一并说明。",
      "",
      "祝好！",
      "[PERSON_1]",
    ),
    translations: {
      en: text(
        "Hi [PERSON_1],",
        "",
        "Thank you for your reply. We need to move about 12 pallets a week at 2 to 4°C, and would like to start in the first week of November.",
        "",
        "Could you send us the quote before this Friday? Also, is there a discount for a one-year contract?",
        "",
        "[PERSON_2]",
        "Penang Fresh Sdn Bhd",
      ),
      ms: text(
        "Hai [PERSON_1],",
        "",
        "Terima kasih atas balasan anda. Kami perlu menghantar kira-kira 12 palet seminggu pada suhu 2 hingga 4°C, dan ingin bermula pada minggu pertama November.",
        "",
        "Bolehkah sebut harga dihantar kepada kami sebelum Jumaat ini? Selain itu, adakah diskaun jika kami menandatangani kontrak setahun?",
        "",
        "[PERSON_2]",
        "Penang Fresh Sdn Bhd",
      ),
    },
  },

  "demo-payslip": {
    translations: {
      ms: text(
        "Slip gaji anda bagi bulan September 2026 kini boleh didapati di portal HR.",
        "",
        "Ini ialah mesej automatik. Sila jangan balas.",
      ),
      zh: text(
        "您 2026 年 9 月的工资单现已可在 HR 系统中查看。",
        "",
        "这是一封自动发送的邮件，请勿回复。",
      ),
    },
  },

  "demo-kenduri": {
    otherTone: {
      professional: text(
        "Salam [PERSON_3],",
        "",
        "Terima kasih atas jemputan ke majlis perkahwinan [PERSON_2]. Insya-Allah saya akan hadir pada 25 Oktober, dan saya akan memaklumkan bilangan tetamu sebelum 20 Oktober.",
        "",
        "Tahniah kepada [PERSON_2] dan keluarga.",
        "",
        "Sekian, terima kasih.",
        "",
        "[PERSON_1]",
      ),
    },
    direct: text(
      "Salam [PERSON_3],",
      "",
      "Insya-Allah saya datang pada 25 Oktober. Nanti saya beritahu berapa orang sebelum 20 Oktober.",
      "",
      "[PERSON_1]",
    ),
    deadline: text(
      "Salam [PERSON_3],",
      "",
      "Terima kasih atas jemputan! Insya-Allah saya akan datang pada 25 Oktober. Saya akan beritahu berapa orang yang akan datang paling lewat 18 Oktober, sebelum tarikh akhir katering.",
      "",
      "Tahniah kepada [PERSON_2] sekeluarga!",
      "",
      "[PERSON_1]",
    ),
    translations: {
      en: text(
        "Hi [PERSON_1],",
        "",
        "I'd like to invite you to my younger brother [PERSON_2]'s wedding on Saturday, 25 October, from 12pm to 4pm at [LOCATION_1].",
        "",
        "If you can, let me know before 20 October how many people are coming, as we need to confirm the catering numbers.",
        "",
        "Thank you!",
        "[PERSON_3]",
      ),
      zh: text(
        "[PERSON_1] 你好，",
        "",
        "我想邀请你参加我弟弟 [PERSON_2] 的婚礼，时间是 10 月 25 日（星期六）中午 12 点至下午 4 点，地点在 [LOCATION_1]。",
        "",
        "方便的话，请在 10 月 20 日前告诉我会有几位出席，因为我们需要确认餐饮人数。",
        "",
        "谢谢！",
        "[PERSON_3]",
      ),
    },
  },
};

/** Drafts that appear only once the reader confirms a sender whose checks failed. */
export const DEMO_CONFIRMED_DRAFTS: Readonly<Record<string, string>> = {
  "demo-ceo-transfer": text(
    "Hi [PERSON_2],",
    "",
    "I've received your request. Under our payment procedure, a new account must be confirmed by phone with Finance before any transfer, so I'll call your office on the usual number before doing anything.",
    "",
    "Regards,",
    "[PERSON_1]",
  ),
};
