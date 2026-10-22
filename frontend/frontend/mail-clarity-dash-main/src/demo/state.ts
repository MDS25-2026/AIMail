import { ApiError, ApiErrorCode } from "../lib/api/errors";
import { en } from "../locales/en";
import { ms } from "../locales/ms";
import { zh } from "../locales/zh";
import {
  ActionGroup,
  AuditVerification,
  type AuditFields,
  type AuditTrailEvent,
} from "../types/audit";
import type { ComposeDraft } from "../types/compose";
import { MaskingStatus, type Email } from "../types/email";
import type { DocumentDetail } from "../types/knowledge";
import type { WritingStyle } from "../types/profile";
import type { HoldingReplySettings, QuietHours, ScanReading } from "../types/settings";
import type { Template } from "../types/template";
import { demoComposeDrafts } from "./data/compose";
import { DEMO_DOCUMENTS } from "./data/documents";
import { DEMO_ACCOUNT, DEMO_WAITING_EMAIL_ID, demoEmails } from "./data/emails";
import {
  DEMO_HOLDING_REPLY,
  DEMO_SCAN_READING,
  DEMO_WAITING_DAYS,
  demoWritingStyle,
} from "./data/settings";
import { DEMO_TEMPLATES } from "./data/templates";

/**
 * What the demo has changed since the page loaded, in memory only: a reload starts afresh. The
 * routes in request.ts (emails) and pages.ts (everything else) read and change it.
 */

export type Json = Record<string, unknown>;
export type Call = { params: string[]; json: Json; query: URLSearchParams; endpoint: string };
export type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
/** thinks: an AI action, answered after the model's usual pause. */
export type Route = {
  method: Method;
  pattern: RegExp;
  handler: (call: Call) => unknown;
  thinks?: boolean;
};

const NOT_IN_DEMO = 400;
const NOT_FOUND = 404;

// The refine suggestions, in every language the reader may have picked: only these are prepared.
export const SUGGESTED = {
  direct: new Set([en, ms, zh].map((locale) => locale.refine.suggestionDirect)),
  deadline: new Set([en, ms, zh].map((locale) => locale.refine.suggestionDeadline)),
};

export function notInDemo(endpoint: string): never {
  throw new ApiError(NOT_IN_DEMO, ApiErrorCode.NotInDemo, endpoint);
}

export function notFound(endpoint: string): never {
  throw new ApiError(NOT_FOUND, ApiErrorCode.NotFound, endpoint);
}

type DemoState = {
  /** The mailbox as it started, for the drafts' first tone. */
  start: Email[];
  emails: Email[];
  /** No reply needed (To-do), by email id, with when. */
  dismissed: Map<string, string>;
  /** Not waiting, by sent id, with when. */
  notWaiting: Map<string, string>;
  /** Follow-ups sent, by sent id, with when. */
  followedUp: Map<string, string>;
  waitingDays: number;
  audit: AuditTrailEvent[];
  templates: Template[];
  documents: DocumentDetail[];
  holdingReply: HoldingReplySettings;
  personalQuietHours: QuietHours | null;
  scanReading: ScanReading;
  writingStyle: WritingStyle | null;
  /** New emails on the Compose page, drafts and sent. */
  composeDrafts: ComposeDraft[];
};

/** The mailbox as it starts, with its times counted back from `now`. */
function freshState(now: Date): DemoState {
  const emails = demoEmails(now);
  return {
    start: emails,
    emails: structuredClone(emails),
    dismissed: new Map(),
    notWaiting: new Map(),
    followedUp: new Map(),
    waitingDays: DEMO_WAITING_DAYS,
    audit: [],
    templates: [...structuredClone(DEMO_TEMPLATES)],
    documents: [...structuredClone(DEMO_DOCUMENTS)],
    holdingReply: structuredClone(DEMO_HOLDING_REPLY),
    personalQuietHours: null,
    scanReading: structuredClone(DEMO_SCAN_READING),
    writingStyle: demoWritingStyle(now),
    composeDrafts: demoComposeDrafts(now),
  };
}

export const state: DemoState = freshState(new Date());

/** Back to the mailbox as it starts: each time a visitor starts the demo (#236 review), so the
 *  next one at the booth never sees the last one's sends, and for tests. */
export function resetDemo(now = new Date()) {
  Object.assign(state, freshState(now));
  seedAudit(state.start);
}

export function findEmail(id: string, endpoint: string): Email {
  return state.emails.find((email) => email.id === id) ?? notFound(endpoint);
}

/** Change one email in place and answer with it, as the backend's email actions do. */
export function updateEmail(
  { params, endpoint }: Call,
  change: (email: Email) => Partial<Email>,
): Email {
  const email = findEmail(params[0], endpoint);
  Object.assign(email, change(email));
  return email;
}

// backend/app/audit_groups.py, for the actions the demo records; any other falls to Other there too.
const DEMO_GROUPS: readonly (readonly [ActionGroup, readonly string[]])[] = [
  [
    ActionGroup.Sending,
    [
      "approve_and_send",
      "follow_up_sent",
      "send_scheduled",
      "scheduled_send_cancelled",
      "compose_sent",
    ],
  ],
  [
    ActionGroup.Drafting,
    [
      "generate_draft",
      "refine_draft",
      "translate_email",
      "template_used",
      "compose_written",
      "compose_refined",
      "compose_deleted",
    ],
  ],
  [ActionGroup.Privacy, ["store_message", "confirm_sender", "scan_reading"]],
  [ActionGroup.Mailbox, ["email_snoozed", "email_dismissed", "waiting_dismissed"]],
  [
    ActionGroup.Settings,
    [
      "quiet_hours",
      "todo_settings",
      "holding_reply_settings",
      "template_saved",
      "template_deleted",
      "document_deleted",
      "writing_style_description",
      "writing_style_learning",
      "writing_style_example_added",
      "writing_style_deleted_example",
      "writing_style_hid_habit",
      "writing_style_deleted",
    ],
  ],
];
const GROUP_OF: ReadonlyMap<string, ActionGroup> = new Map(
  DEMO_GROUPS.flatMap(([group, actions]) => actions.map((action) => [action, group] as const)),
);

/** One audit row, the visitor's own; its hashes are filled in when the trail is read (chainedAudit). */
export function record(action: string, fields: AuditFields, at = new Date()) {
  state.audit.push({
    id: `demo-audit-${state.audit.length + 1}`,
    action,
    group: GROUP_OF.get(action) ?? ActionGroup.Other,
    userEmail: DEMO_ACCOUNT,
    createdAt: at.toISOString(),
    fields,
    success: true,
    prevHash: null,
    currentHash: null,
    verification: AuditVerification.Verified,
  });
}

// backend/app/db/migrations/0024: concat_ws(chr(31), …), the first row chained to 64 zeros.
const SEPARATOR = String.fromCharCode(31);
const GENESIS_HASH = "0".repeat(64);

/** audit_detail() in backend/app/audit.py: compact JSON with sorted keys. ASCII only here, as
 *  Python's json.dumps escapes anything else. */
function canonicalDetail(fields: AuditFields): string {
  const sorted = Object.fromEntries(Object.entries(fields).sort(([a], [b]) => (a < b ? -1 : 1)));
  return JSON.stringify(sorted);
}

/** extract(epoch FROM created_at)::text: seconds with six decimals. */
function epochText(iso: string): string {
  const ms = new Date(iso).getTime();
  return `${Math.floor(ms / 1000)}.${String(ms % 1000).padStart(3, "0")}000`;
}

/** Whether this browser can hash: crypto.subtle needs https or localhost. */
export const canHash = () => typeof globalThis.crypto?.subtle?.digest === "function";

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** The trail, oldest first, hashed by the database's own formula (audit_row_hash in migration
 *  0024): SHA-256(prev_hash | sequence | action | detail | success | user_id | timestamp), the
 *  fields joined by chr(31). The demo has no user id, so that field is empty, as for a system row. */
export async function chainedAudit(): Promise<AuditTrailEvent[]> {
  const chained: AuditTrailEvent[] = [];
  let prevHash = GENESIS_HASH;
  for (const [index, event] of state.audit.entries()) {
    const fields = [
      prevHash,
      String(index + 1),
      event.action,
      canonicalDetail(event.fields),
      String(event.success ?? ""),
      "",
      epochText(event.createdAt),
    ];
    const currentHash = await sha256(fields.join(SEPARATOR));
    chained.push({ ...event, prevHash, currentHash });
    prevHash = currentHash;
  }
  return chained;
}

/** What the listener and the agent recorded for the mailbox before the visitor arrived. */
function seedAudit(emails: Email[]) {
  const steps = emails.flatMap((email) => {
    const at = new Date(email.timestamp);
    const masked = email.details?.length ?? 0;
    const emailsMasked = email.details?.filter((d) => d.kind === "EMAIL").length ?? 0;
    const phonesMasked = email.details?.filter((d) => d.kind === "PHONE").length ?? 0;
    const rows: [string, AuditFields, Date][] = [
      [
        "store_message",
        {
          emails_masked: emailsMasked,
          gmail_message_id: email.id,
          phones_masked: phonesMasked,
        },
        at,
      ],
    ];
    if (email.draftReply) {
      const drafted = new Date(at.getTime() + 60_000);
      const review = (email.reviewReasons?.length ?? 0) > 0;
      const fields = {
        message: email.id,
        tone: email.tone,
        confidence: email.criticConfidence,
        review,
      };
      rows.push(["generate_draft", fields, drafted]);
    }
    if (email.id === DEMO_WAITING_EMAIL_ID && email.sentAt) {
      rows.push([
        "approve_and_send",
        { message: email.id, restored: masked },
        new Date(email.sentAt),
      ]);
    }
    return rows;
  });
  steps
    .sort(([, , a], [, , b]) => a.getTime() - b.getTime())
    .forEach(([action, fields, at]) => record(action, fields, at));
}

seedAudit(state.start);
