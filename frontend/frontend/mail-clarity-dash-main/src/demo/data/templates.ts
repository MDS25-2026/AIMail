import { Language } from "../../lib/preferences";
import type { Template } from "../../types/template";

/** Saved replies in the demo, one per language; {{variables}} fill in as on the backend. */
export const DEMO_TEMPLATES: readonly Template[] = [
  {
    id: "demo-template-invoice",
    title: "Invoice received",
    language: Language.English,
    triggerKeywords: ["invoice"],
    body: [
      "Hi {{name}},",
      "",
      "Thank you, we have received your invoice and passed it to Finance. We will confirm the payment date within two working days.",
      "",
      "Best regards,",
      "{{my name}}",
    ].join("\n"),
  },
  {
    id: "demo-template-bayaran",
    title: "Bayaran sedang disemak",
    language: Language.Malay,
    triggerKeywords: ["invois", "bayaran"],
    body: [
      "Salam {{nama}},",
      "",
      "Terima kasih atas e-mel anda. Kami sedang menyemak status bayaran dengan bahagian kewangan dan akan memaklumkan tarikh bayaran dalam masa dua hari bekerja.",
      "",
      "Sekian, terima kasih.",
      "",
      "{{nama saya}}",
    ].join("\n"),
  },
  {
    id: "demo-template-received",
    title: "已收到，稍后回复",
    language: Language.Chinese,
    triggerKeywords: ["报价"],
    body: [
      "{{名字}} 你好，",
      "",
      "已收到你的邮件（{{今天}}），谢谢。我会尽快回复具体安排。",
      "",
      "祝好！",
      "{{我的名字}}",
    ].join("\n"),
  },
];
