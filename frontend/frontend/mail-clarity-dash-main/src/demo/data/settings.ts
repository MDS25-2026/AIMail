import { Language } from "../../lib/preferences";
import type { SystemInfo } from "../../types/knowledge";
import { ExampleSource, StyleHabitKind, type WritingStyle } from "../../types/profile";
import {
  ActiveWhen,
  Audience,
  ReplyScope,
  ScanMode,
  type HoldingReplySettings,
  type PrivateMode,
  type QuietHours,
  type ScanReading,
} from "../../types/settings";

/** Settings as a new account starts them: the backend's defaults (holding_reply.py, quiet_hours.py). */

export const DEMO_WAITING_DAYS = 3;

export const DEMO_COMPANY_QUIET_HOURS: QuietHours = {
  start: "21:00:00",
  end: "08:00:00",
  weekendDays: [6, 7],
  timezone: "Asia/Kuala_Lumpur",
};

export const DEMO_HOLDING_REPLY: HoldingReplySettings = {
  enabled: false,
  activeWhen: ActiveWhen.OutsideHours,
  workDays: [1, 2, 3, 4, 5],
  workStart: "09:00:00",
  workEnd: "18:00:00",
  timezone: "Asia/Kuala_Lumpur",
  leaveFrom: null,
  leaveUntil: null,
  audience: Audience.Correspondents,
  scope: ReplyScope.NeedsReply,
  cooldownDays: 4,
  templates: {},
  defaultLanguage: Language.English,
};

// The demo has no local model, so Private mode and checked scan reading are not offered, as on an
// install without one.
export const DEMO_PRIVATE_MODE: PrivateMode = {
  available: false,
  enabled: false,
  isDecided: true,
  model: "",
  search: false,
};

export const DEMO_SCAN_READING: ScanReading = { available: false, mode: ScanMode.Local };

/** A writing style learned from a few sent replies, so the card shows what it does. */
export function demoWritingStyle(now: Date): WritingStyle {
  return {
    description: "Polite and to the point. Short paragraphs; sign off with my first name.",
    learning: true,
    maxExamples: 3,
    examples: [
      {
        id: "demo-example-1",
        source: ExampleSource.Sent,
        createdAt: new Date(now.getTime() - 7 * 24 * 60 * 60_000).toISOString(),
        text: "Hi [PERSON_2],\n\nThanks for letting us know. Tuesdays and Thursdays work for us, but our loading bay is busy before 10am. Could your drivers arrive between 10am and 3pm on those days?\n\nBest regards,\n[PERSON_1]",
      },
    ],
    habits: [
      {
        id: "demo-habit-greeting",
        kind: StyleHabitKind.Greeting,
        value: "Hi",
        evidence: 4,
        outOf: 5,
        language: Language.English,
      },
      {
        id: "demo-habit-signoff",
        kind: StyleHabitKind.Signoff,
        value: "Best regards",
        evidence: 3,
        outOf: 5,
        language: Language.English,
      },
    ],
  };
}

/** The real app's configuration (backend/app/core/constants.py, config.py), so Settings reads true. */
export const DEMO_SYSTEM_INFO: Omit<SystemInfo, "document_count" | "chunk_count"> = {
  chat_model: "gemini-2.5-flash",
  embedding_model: "gemini-embedding-001",
  embedding_dim: 1536,
  priority_model: "baseline",
  auth_enabled: true,
  auto_generate: true,
  generate_poll_seconds: 60,
};
