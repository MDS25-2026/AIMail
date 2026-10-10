/** Holding reply, Private mode and scan settings (holding-reply.md, local-model.md, signature-detection.md). */
import type { Language } from "../lib/preferences";
import { assertSameValues, type Schemas, type WithEnums } from "./schema";

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

/** Required: the same model is the request body, where its defaults make fields optional; reads have all. */
export type HoldingReplySettings = WithEnums<
  Required<Schemas["SettingsBody"]>,
  {
    activeWhen: ActiveWhen;
    audience: Audience;
    scope: ReplyScope;
    templates: Partial<Record<Language, string>>;
    defaultLanguage: Language;
  }
>;

/** cancelledReason is a CancelReason; a newer backend may send one this build does not know yet. */
export type HoldingReplyRecord = Schemas["HoldingReplyView"];

/** Not offered when `available` is false. */
export type PrivateMode = Schemas["PrivateModeView"];

/** How scanned attachments are read (specs/features/signature-detection.md). */
export enum ScanMode {
  Local = "local",
  Checked = "checked",
}

/** `available`: the company set up the local vision model that checked scans need. */
export type ScanReading = WithEnums<Schemas["ScanReadingView"], { mode: ScanMode }>;

assertSameValues<`${ActiveWhen}`, Schemas["ActiveWhen"]>(true);
assertSameValues<`${ScanMode}`, Schemas["ScanReading"]>(true);
assertSameValues<`${Audience}`, Schemas["Audience"]>(true);
assertSameValues<`${ReplyScope}`, Schemas["ReplyScope"]>(true);

/** Quiet hours (specs/features/quiet-hours-send-later.md): a window and whole weekend days. */
export type QuietHours = Schemas["QuietHoursView"];

/** `personal` is null while the reader follows the company default. */
export type QuietHoursSettings = Schemas["QuietHoursSettings"];
