/** Holding reply and Private mode settings (specs/features/holding-reply.md, local-model.md). */
import type { Language } from "../lib/preferences";

export enum ActiveWhen {
  OutsideHours = "outside_hours",
  Leave = "leave",
  Always = "always",
}

export enum Audience {
  Correspondents = "correspondents",
  Domain = "domain",
  Everyone = "everyone",
}

export enum ReplyScope {
  NeedsReply = "needs_reply",
  All = "all",
}

/** Why a holding reply was not sent (backend/app/holding_reply.py Refusal). */
export enum CancelReason {
  Disabled = "disabled",
  BeforeEnabled = "before_enabled",
  MaskingPending = "masking_pending",
  Automated = "automated",
  Phishing = "phishing",
  ReplyToDiffers = "reply_to_differs",
  NotActive = "not_active",
  OutsideDomain = "outside_domain",
  NoSender = "no_sender",
  NoTemplate = "no_template",
  Stale = "stale",
  UserReplied = "user_replied",
  Cooldown = "cooldown",
  DailyCap = "daily_cap",
  NoReplyNeeded = "no_reply_needed",
  NotCorrespondent = "not_correspondent",
  NoThread = "no_thread",
  CancelledByUser = "cancelled_by_user",
  Other = "other",
}

export type HoldingReplySettings = {
  enabled: boolean;
  activeWhen: ActiveWhen;
  workDays: number[];
  workStart: string;
  workEnd: string;
  timezone: string;
  leaveFrom: string | null;
  leaveUntil: string | null;
  audience: Audience;
  scope: ReplyScope;
  cooldownDays: number;
  templates: Partial<Record<Language, string>>;
  defaultLanguage: Language;
};

export type HoldingReplyRecord = {
  id: string;
  emailId: string;
  recipient: string;
  language: string;
  scheduledFor: string;
  sentAt: string | null;
  /** A CancelReason; a newer backend may send one this build does not know yet. */
  cancelledReason: string | null;
  subject: string;
};

/** Not offered when `available` is false. */
export type PrivateMode = { available: boolean; enabled: boolean; model: string; search: boolean };
