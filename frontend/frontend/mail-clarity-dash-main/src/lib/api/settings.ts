import type { SystemInfo } from "../../types/knowledge";
import type {
  HoldingReplyRecord,
  HoldingReplySettings,
  PrivateMode,
  ScanMode,
  ScanReading,
} from "../../types/settings";
import { HttpMethod, request } from "./client";

const RECENT_HOLDING_REPLIES = 20;

/** Non-secret runtime configuration, for the Settings view. */
export const fetchSystemInfo = () => request<SystemInfo>("/system/info");

export const fetchHoldingReplySettings = () =>
  request<HoldingReplySettings>("/settings/holding-reply");

export const saveHoldingReplySettings = (settings: HoldingReplySettings) =>
  request<HoldingReplySettings>("/settings/holding-reply", {
    method: HttpMethod.Put,
    json: settings,
  });

export const fetchHoldingReplies = () =>
  request<HoldingReplyRecord[]>(`/holding-replies?limit=${RECENT_HOLDING_REPLIES}`);

export const cancelHoldingReply = (id: string) =>
  request<void>(`/holding-replies/${encodeURIComponent(id)}`, { method: HttpMethod.Delete });

export const fetchPrivateMode = () => request<PrivateMode>("/settings/private-mode");

export const savePrivateMode = (enabled: boolean) =>
  request<PrivateMode>("/settings/private-mode", { method: HttpMethod.Put, json: { enabled } });

export const fetchScanReading = () => request<ScanReading>("/settings/scan-reading");

export const saveScanReading = (mode: ScanMode) =>
  request<ScanReading>("/settings/scan-reading", { method: HttpMethod.Put, json: { mode } });
