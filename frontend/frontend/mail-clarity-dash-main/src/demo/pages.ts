import { ApiError, ApiErrorCode } from "../lib/api/errors";
import { Language } from "../lib/preferences";
import type { AuditTrail } from "../types/audit";
import { AuthStatus, MaskingStatus, type Email } from "../types/email";
import type { DocumentDetail, PolicyDocument, SystemInfo } from "../types/knowledge";
import { ExampleSource, type WritingStyle } from "../types/profile";
import {
  ScanMode,
  type HoldingReplySettings,
  type QuietHours,
  type QuietHoursSettings,
} from "../types/settings";
import type { Template } from "../types/template";
import type { FollowUpDraft, Todo, TodoSection, WaitingReply } from "../types/todo";
import { DEMO_FOLLOW_UPS } from "./data/answers";
import { DEMO_OWNER_NAME } from "./data/emails";
import { DEMO_COMPANY_QUIET_HOURS, DEMO_PRIVATE_MODE, DEMO_SYSTEM_INFO } from "./data/settings";
import {
  canHash,
  chainedAudit,
  findEmail,
  notFound,
  notInDemo,
  record,
  state,
  type Call,
  type Route,
} from "./state";

/** The demo's answers for every page but the inbox: To-do, Audit, Templates, Knowledge, Settings. */

const TOO_MANY = 400;
const INVALID = 400;
const DAY_MS = 24 * 60 * 60_000;
// Drafts left unsent this long are listed again (backend/app/todo.py DRAFT_REMINDER_AFTER).
const DRAFT_REMINDER_MS = DAY_MS;
const PRIORITY_RANK: Record<Email["priority"], number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

// ---- To-do (backend/app/todo.py) ----

/** Unsent, readable, not dismissed, not a spoof, written by a person, and not snoozed. */
function isOpen(email: Email, now: Date): boolean {
  const isSnoozed = email.snoozedUntil ? new Date(email.snoozedUntil) > now : false;
  return (
    !email.sentAt &&
    !state.dismissed.has(email.id) &&
    email.masking === MaskingStatus.Complete &&
    email.authStatus !== AuthStatus.SpoofDetected &&
    !email.isAutomated &&
    !isSnoozed
  );
}

/** Each email in one list only, the most urgent: review, then action, then an unsent draft. */
type SectionName = "needsAction" | "needsReview" | "unsentDrafts";

function sectionOf(email: Email, now: Date): SectionName | null {
  if (!isOpen(email, now)) return null;
  const hasDraft = email.draftReply !== "";
  if (hasDraft && (email.reviewReasons?.length ?? 0) > 0) return "needsReview";
  if (email.actionItems.length > 0) return "needsAction";
  const isStale = now.getTime() - new Date(email.timestamp).getTime() > DRAFT_REMINDER_MS;
  return hasDraft && isStale ? "unsentDrafts" : null;
}

/** Most urgent first; within a priority, the longest waiting first. */
const byUrgency = (a: Email, b: Email) =>
  PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] || a.timestamp.localeCompare(b.timestamp);

function section(name: SectionName, now: Date): TodoSection {
  const emails = state.emails.filter((email) => sectionOf(email, now) === name).sort(byUrgency);
  return { emails, total: emails.length };
}

/** ISO weekday, 1 (Monday) to 7 (Sunday), as quiet hours store the weekend. */
const isoWeekday = (day: Date) => day.getDay() || 7;

/** Working days between the two days, not counting the first; the weekend is the reader's quiet
 *  hours' (backend/app/waiting.py working_days_since). */
function workingDaysSince(since: Date, now: Date): number {
  const weekend = new Set(quietHours().effective.weekendDays);
  let days = 0;
  for (
    let day = new Date(since.getTime() + DAY_MS);
    day <= now;
    day = new Date(day.getTime() + DAY_MS)
  ) {
    if (!weekend.has(isoWeekday(day))) days += 1;
  }
  return days;
}

const sentIdOf = (email: Email) => `sent-${email.id}`;

/** Replies that asked something and have had no answer for the reader's number of working days. */
function waiting(now: Date): WaitingReply[] {
  return state.emails.flatMap((email) => {
    const sentId = sentIdOf(email);
    if (!email.sentAt || state.notWaiting.has(sentId) || state.followedUp.has(sentId)) return [];
    if (!/[?？]/.test(email.draftReply)) return [];
    const workingDays = workingDaysSince(new Date(email.sentAt), now);
    if (workingDays < state.waitingDays) return [];
    return [
      {
        id: sentId,
        subject: email.subject,
        sentAt: email.sentAt,
        threadId: email.threadId ?? email.id,
        workingDays,
        email,
        canFollowUp: true,
      },
    ];
  });
}

function emailOfSent(sentId: string, endpoint: string): Email {
  return state.emails.find((email) => sentIdOf(email) === sentId) ?? notFound(endpoint);
}

function startOfToday(now: Date): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

/** Emails sent or dismissed, and replies not waited on or followed up, since midnight: each once,
 *  as the backend counts live columns, so dismissed and then sent is one. */
function doneToday(now: Date): number {
  const since = startOfToday(now).toISOString();
  const isToday = (at: string | null | undefined) => (at ?? "") >= since;
  const emails = state.emails.filter(
    (email) => isToday(email.sentAt) || isToday(state.dismissed.get(email.id)),
  ).length;
  const replies = new Set(
    [...state.notWaiting, ...state.followedUp].filter(([, at]) => isToday(at)).map(([id]) => id),
  );
  return emails + replies.size;
}

function todo(): Todo {
  const now = new Date();
  const sections = {
    needsAction: section("needsAction", now),
    needsReview: section("needsReview", now),
    unsentDrafts: section("unsentDrafts", now),
  };
  const replies = waiting(now);
  const count =
    sections.needsAction.total + sections.needsReview.total + sections.unsentDrafts.total;
  return {
    ...sections,
    waiting: replies,
    waitingDays: state.waitingDays,
    count: count + replies.length,
    doneToday: doneToday(now),
  };
}

function markDismissed(call: Call, isDismissed: boolean) {
  const email = findEmail(call.params[0], call.endpoint);
  if (isDismissed) state.dismissed.set(email.id, new Date().toISOString());
  else state.dismissed.delete(email.id);
  record("email_dismissed", { message: email.id, dismissed: isDismissed });
}

function markNotWaiting({ params, endpoint }: Call, isDismissed: boolean) {
  emailOfSent(params[0], endpoint);
  if (isDismissed) state.notWaiting.set(params[0], new Date().toISOString());
  else state.notWaiting.delete(params[0]);
  record("waiting_dismissed", { sent: params[0], dismissed: isDismissed });
}

// ---- Templates (backend/app/templates.py) ----

const MALAY_MONTHS = [
  "Januari",
  "Februari",
  "Mac",
  "April",
  "Mei",
  "Jun",
  "Julai",
  "Ogos",
  "September",
  "Oktober",
  "November",
  "Disember",
];
const ENGLISH_MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function formatDay(day: Date, language: Language): string {
  if (language === Language.Chinese) {
    return `${day.getFullYear()}年${day.getMonth() + 1}月${day.getDate()}日`;
  }
  const months = language === Language.Malay ? MALAY_MONTHS : ENGLISH_MONTHS;
  return `${day.getDate()} ${months[day.getMonth()]} ${day.getFullYear()}`;
}

const VARIABLE = /\{\{([^{}]*)\}\}/g;
const ALIASES: Record<string, "name" | "my name" | "today"> = {
  name: "name",
  nama: "name",
  姓名: "name",
  名字: "name",
  "my name": "my name",
  "nama saya": "my name",
  我的名字: "my name",
  today: "today",
  "hari ini": "today",
  今天: "today",
};

/** The placeholder that stands for a person in this email, found by the name it hides. */
function placeholderFor(email: Email, name: string | undefined): string | undefined {
  if (!name) return undefined;
  return email.details?.find((detail) => detail.kind === "PERSON" && name.includes(detail.value))
    ?.placeholder;
}

/** The sender's and the reader's names as placeholders, and today's date; anything else as written. */
function fillTemplate(template: Template, email: Email): string {
  const senderName = email.sender.split("<")[0].trim();
  const values = {
    name: placeholderFor(email, senderName),
    "my name": placeholderFor(email, DEMO_OWNER_NAME),
    today: formatDay(new Date(), template.language),
  };
  return template.body.replace(VARIABLE, (whole, raw: string) => {
    const variable = ALIASES[raw.trim().toLowerCase().split(/\s+/).join(" ")];
    return (variable && values[variable]) || whole;
  });
}

function findTemplate(id: string, endpoint: string): Template {
  return state.templates.find((template) => template.id === id) ?? notFound(endpoint);
}

const isLanguage = (value: unknown): value is Language =>
  Object.values<unknown>(Language).includes(value);

const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];

function templateFrom(json: Call["json"], id: string): Template {
  return {
    id,
    title: String(json.title ?? ""),
    body: String(json.body ?? ""),
    language: isLanguage(json.language) ? json.language : Language.English,
    triggerKeywords: strings(json.triggerKeywords),
    lastUsedAt: null,
  };
}

// ---- Knowledge ----

const summaryOf = (document: DocumentDetail): PolicyDocument => ({
  document_id: document.document_id,
  title: document.title,
  source: document.source,
  doc_type: document.doc_type,
  chunk_count: document.chunk_count,
});

function findDocument(id: string, endpoint: string): DocumentDetail {
  return state.documents.find((document) => document.document_id === id) ?? notFound(endpoint);
}

/** Pasted text, one chunk per paragraph; kept in memory like everything else in the demo. */
function addDocument(json: Call["json"]): { chunks: number } {
  const id = `demo-doc-${Date.now()}`;
  const paragraphs = String(json.text ?? "")
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  state.documents.push({
    document_id: id,
    title: String(json.title ?? ""),
    source: "pasted",
    doc_type: "policy",
    chunk_count: paragraphs.length,
    content: paragraphs.join("\n\n"),
    chunks: paragraphs.map((content, index) => ({
      id: `${id}-chunk-${index}`,
      chunk_idx: index,
      section: null,
      content,
    })),
  });
  return { chunks: paragraphs.length };
}

// ---- Settings ----

/** The backend's template checks (holding_reply.py _template_errors) that a visitor can hit. */
function holdingReplyError(settings: HoldingReplySettings): ApiErrorCode | null {
  if (Object.values(settings.templates).some((text) => !text?.trim())) {
    return ApiErrorCode.EmptyTemplate;
  }
  if (settings.enabled && !settings.templates[settings.defaultLanguage]) {
    return ApiErrorCode.NoDefaultTemplate;
  }
  return null;
}

/** ISO weekdays only, 1 (Monday) to 7 (Sunday), as the backend's validator allows. */
function quietHoursFrom(json: Call["json"]): QuietHours {
  const company = DEMO_COMPANY_QUIET_HOURS;
  const weekendDays = Array.isArray(json.weekendDays)
    ? json.weekendDays.filter(
        (day): day is number => typeof day === "number" && day >= 1 && day <= 7,
      )
    : company.weekendDays;
  return {
    start: typeof json.start === "string" ? json.start : company.start,
    end: typeof json.end === "string" ? json.end : company.end,
    timezone: typeof json.timezone === "string" ? json.timezone : company.timezone,
    weekendDays,
  };
}

function quietHours(): QuietHoursSettings {
  const personal = state.personalQuietHours;
  return {
    company: DEMO_COMPANY_QUIET_HOURS,
    effective: personal ?? DEMO_COMPANY_QUIET_HOURS,
    personal,
  };
}

const EMPTY_STYLE: WritingStyle = {
  description: "",
  learning: false,
  maxExamples: 3,
  examples: [],
  habits: [],
};

function writingStyle(): WritingStyle {
  return state.writingStyle ?? EMPTY_STYLE;
}

function changeStyle(
  action: string,
  fields: AuditFields,
  change: (style: WritingStyle) => Partial<WritingStyle>,
) {
  const style = writingStyle();
  state.writingStyle = { ...style, ...change(style) };
  record(action, fields);
  return state.writingStyle;
}

function addExample({ json, endpoint }: Call): WritingStyle {
  const style = writingStyle();
  if (style.examples.length >= style.maxExamples) {
    throw new ApiError(TOO_MANY, ApiErrorCode.TooManyExamples, endpoint);
  }
  const fromEmail = typeof json.emailId === "string" ? findEmail(json.emailId, endpoint) : null;
  // Only a reply that went out can be an example (writing_style_routes.py _sent_text).
  if (fromEmail && !fromEmail.sentAt) notFound(endpoint);
  const example = {
    id: `demo-example-${Date.now()}`,
    source: fromEmail ? ExampleSource.Sent : ExampleSource.Pasted,
    createdAt: new Date().toISOString(),
    text: fromEmail ? fromEmail.draftReply : String(json.text ?? ""),
  };
  return changeStyle(
    "writing_style_example_added",
    { source: example.source },
    () => ({
      examples: [...style.examples, example],
    }),
  );
}

export const PAGE_ROUTES: Route[] = [
  // To-do
  { method: "GET", pattern: /^\/todo$/, handler: todo },
  {
    method: "POST",
    pattern: /^\/emails\/([^/]+)\/dismiss$/,
    handler: (call) => markDismissed(call, true),
  },
  {
    method: "DELETE",
    pattern: /^\/emails\/([^/]+)\/dismiss$/,
    handler: (call) => markDismissed(call, false),
  },
  {
    method: "POST",
    pattern: /^\/todo\/waiting\/([^/]+)\/dismiss$/,
    handler: (call) => markNotWaiting(call, true),
  },
  {
    method: "DELETE",
    pattern: /^\/todo\/waiting\/([^/]+)\/dismiss$/,
    handler: (call) => markNotWaiting(call, false),
  },
  {
    method: "POST",
    pattern: /^\/todo\/waiting\/([^/]+)\/follow-up$/,
    thinks: true,
    handler: ({ params, endpoint }): FollowUpDraft => {
      const email = emailOfSent(params[0], endpoint);
      const draft = DEMO_FOLLOW_UPS[email.id] ?? notFound(endpoint);
      return { draft, details: email.details ?? [] };
    },
  },
  {
    method: "POST",
    pattern: /^\/todo\/waiting\/([^/]+)\/follow-up\/send$/,
    // Pretend, like every send in the demo.
    handler: ({ params, endpoint }) => {
      const email = emailOfSent(params[0], endpoint);
      state.followedUp.set(params[0], new Date().toISOString());
      record("follow_up_sent", { message: email.id, restored: email.details?.length ?? 0 });
    },
  },
  {
    method: "PUT",
    pattern: /^\/settings\/todo$/,
    handler: ({ json }) => {
      state.waitingDays = Number(json.waitingDays) || state.waitingDays;
      record("todo_settings", { waiting_days: state.waitingDays });
      return { waitingDays: state.waitingDays };
    },
  },

  // Audit
  {
    method: "GET",
    pattern: /^\/audit$/,
    handler: async ({ endpoint }): Promise<AuditTrail> => {
      // Hashing needs https or localhost; on plain http the page says so rather than crashing.
      if (!canHash()) return notInDemo(endpoint);
      const events = (await chainedAudit()).reverse();
      return {
        events,
        isChainIntact: true,
        totalRecords: events.length,
        verifiedRecords: events.length,
        headHash: events[0]?.currentHash ?? null,
      };
    },
  },

  // Templates
  { method: "GET", pattern: /^\/templates$/, handler: () => state.templates },
  {
    method: "POST",
    pattern: /^\/templates$/,
    handler: ({ json }) => {
      const template = templateFrom(json, `demo-template-${Date.now()}`);
      state.templates.push(template);
      record("template_saved", { template: template.id });
      return template;
    },
  },
  {
    method: "PUT",
    pattern: /^\/templates\/([^/]+)$/,
    handler: ({ params, json, endpoint }) => {
      const template = findTemplate(params[0], endpoint);
      Object.assign(template, templateFrom(json, template.id), { lastUsedAt: template.lastUsedAt });
      record("template_saved", { template: template.id });
      return template;
    },
  },
  {
    method: "DELETE",
    pattern: /^\/templates\/([^/]+)$/,
    handler: ({ params, endpoint }) => {
      findTemplate(params[0], endpoint);
      state.templates = state.templates.filter((template) => template.id !== params[0]);
      record("template_deleted", { template: params[0] });
    },
  },
  {
    method: "POST",
    pattern: /^\/templates\/([^/]+)\/fill$/,
    handler: ({ params, json, endpoint }) => {
      const template = findTemplate(params[0], endpoint);
      const email = findEmail(String(json.emailId), endpoint);
      template.lastUsedAt = new Date().toISOString();
      record("template_used", { template: template.id, mode: "insert" });
      return { text: fillTemplate(template, email) };
    },
  },

  // Knowledge
  {
    method: "GET",
    pattern: /^\/documents$/,
    handler: () => state.documents.map(summaryOf),
  },
  {
    method: "GET",
    pattern: /^\/documents\/([^/]+)$/,
    handler: ({ params, endpoint }) => findDocument(params[0], endpoint),
  },
  {
    method: "DELETE",
    pattern: /^\/documents\/([^/]+)$/,
    handler: ({ params, endpoint }) => {
      findDocument(params[0], endpoint);
      state.documents = state.documents.filter((document) => document.document_id !== params[0]);
      record("document_deleted", { document: params[0] });
    },
  },
  { method: "POST", pattern: /^\/documents$/, handler: ({ json }) => addDocument(json) },
  {
    method: "GET",
    pattern: /^\/system\/info$/,
    handler: (): SystemInfo => ({
      ...DEMO_SYSTEM_INFO,
      document_count: state.documents.length,
      chunk_count: state.documents.reduce((sum, document) => sum + document.chunk_count, 0),
    }),
  },

  // Settings
  {
    method: "GET",
    pattern: /^\/settings\/holding-reply$/,
    handler: () => state.holdingReply,
  },
  {
    method: "PUT",
    pattern: /^\/settings\/holding-reply$/,
    handler: ({ json, endpoint }) => {
      // The request body is the validation boundary: the form sends the whole settings object.
      const next = { ...state.holdingReply, ...(json as Partial<HoldingReplySettings>) };
      const refused = holdingReplyError(next);
      if (refused) throw new ApiError(INVALID, refused, endpoint);
      state.holdingReply = next;
      record("holding_reply_settings", { enabled: next.enabled });
      return next;
    },
  },
  { method: "GET", pattern: /^\/holding-replies$/, handler: () => [] },
  { method: "GET", pattern: /^\/settings\/private-mode$/, handler: () => DEMO_PRIVATE_MODE },
  { method: "POST", pattern: /^\/settings\/private-mode\/not-now$/, handler: () => undefined },
  { method: "GET", pattern: /^\/settings\/scan-reading$/, handler: () => state.scanReading },
  {
    method: "PUT",
    pattern: /^\/settings\/scan-reading$/,
    handler: ({ json }) => {
      const mode = json.mode === ScanMode.Checked ? ScanMode.Checked : ScanMode.Local;
      state.scanReading = { ...state.scanReading, mode };
      record("scan_reading", { mode: state.scanReading.mode });
      return state.scanReading;
    },
  },
  { method: "GET", pattern: /^\/settings\/quiet-hours$/, handler: quietHours },
  {
    method: "PUT",
    pattern: /^\/settings\/quiet-hours$/,
    handler: ({ json }) => {
      state.personalQuietHours = quietHoursFrom(json);
      record("quiet_hours", { personal: true });
      return quietHours();
    },
  },
  {
    method: "DELETE",
    pattern: /^\/settings\/quiet-hours$/,
    handler: () => {
      state.personalQuietHours = null;
      record("quiet_hours", { personal: false });
      return quietHours();
    },
  },

  // Writing style
  { method: "GET", pattern: /^\/profile\/writing$/, handler: writingStyle },
  {
    method: "PUT",
    pattern: /^\/profile\/writing\/description$/,
    handler: ({ json }) => {
      const description = String(json.description ?? "");
      return changeStyle(
        "writing_style_description",
        { chars: description.length },
        () => ({ description }),
      );
    },
  },
  {
    method: "PUT",
    pattern: /^\/profile\/writing\/learning$/,
    handler: ({ json }) =>
      changeStyle(
        "writing_style_learning",
        { enabled: Boolean(json.enabled) },
        () => ({ learning: Boolean(json.enabled) }),
      ),
  },
  { method: "POST", pattern: /^\/profile\/writing\/examples$/, handler: addExample },
  {
    method: "DELETE",
    pattern: /^\/profile\/writing\/examples\/([^/]+)$/,
    handler: ({ params }) =>
      void changeStyle(
        "writing_style_deleted_example",
        { item: params[0] },
        (style) => ({
          examples: style.examples.filter((example) => example.id !== params[0]),
        }),
      ),
  },
  {
    method: "DELETE",
    pattern: /^\/profile\/writing\/habits\/([^/]+)$/,
    handler: ({ params }) =>
      void changeStyle(
        "writing_style_hid_habit",
        { item: params[0] },
        (style) => ({
          habits: style.habits.filter((habit) => habit.id !== params[0]),
        }),
      ),
  },
  {
    method: "DELETE",
    pattern: /^\/profile\/writing$/,
    handler: () => {
      state.writingStyle = null;
      record("writing_style_deleted", {});
    },
  },
];
