import { ApiError, ApiErrorCode } from "../lib/api/errors";
import { EMPTY_COMPOSE_LIST, withDraft } from "../lib/composeList";
import { detailValues, hasMissingDetails, restoreDetails } from "../lib/details";
import { findRedactionMarkers } from "../lib/draftGuards";
import { ComposeState, type ComposeDraft, type ComposeList } from "../types/compose";
import type { EgressRecord } from "../types/email";
import {
  DEMO_COMPOSE_DETAILS,
  DEMO_COMPOSE_REFINED,
  DEMO_COMPOSE_SOURCES,
  DEMO_COMPOSE_WRITTEN,
} from "./data/compose";
import { notFound, record, state, SUGGESTED, type Call, type Json, type Route } from "./state";

/** Compose's answers (backend/app/compose_routes.py), in memory: a "sent" email goes nowhere. */

const CONFLICT = 409;
const INVALID = 422;
const DEMO_CONFIDENCE = 0.93;

function findDraft({ params, endpoint }: Call): ComposeDraft {
  return state.composeDrafts.find((draft) => draft.id === params[0]) ?? notFound(endpoint);
}

/** Refused once sending or sent, as the backend refuses a change then. */
function editableDraft(call: Call): ComposeDraft {
  const draft = findDraft(call);
  if (draft.state === ComposeState.Sent) {
    throw new ApiError(CONFLICT, ApiErrorCode.AlreadySent, call.endpoint);
  }
  if (draft.state !== ComposeState.Draft) {
    throw new ApiError(CONFLICT, ApiErrorCode.SendInProgress, call.endpoint);
  }
  return draft;
}

/** Typed details back into placeholders, as the backend re-tokenises the values it knows. */
function tokenised(text: string, draft: ComposeDraft): string {
  const known = [...(draft.details ?? [])].sort((a, b) => b.value.length - a.value.length);
  return known.reduce((out, detail) => out.replaceAll(detail.value, detail.placeholder), text);
}

const strings = (value: unknown): string[] | null =>
  Array.isArray(value) ? value.map(String).filter((item) => item.trim()) : null;

/** The fields the call carries into the draft; any left out keep what is stored. */
function apply(draft: ComposeDraft, json: Json): ComposeDraft {
  const text = (key: string) =>
    typeof json[key] === "string" ? tokenised(String(json[key]), draft) : null;
  Object.assign(draft, {
    to: strings(json.to) ?? draft.to,
    cc: strings(json.cc) ?? draft.cc,
    subject: text("subject") ?? draft.subject,
    brief: text("brief") ?? draft.brief,
    body: text("body") ?? draft.body,
    tone: json.tone === "casual" || json.tone === "professional" ? json.tone : draft.tone,
    updatedAt: new Date().toISOString(),
  });
  return draft;
}

/** What a model call adds to the privacy receipt: the brief, details hidden. */
function aiSteps(draft: ComposeDraft, ...purposes: string[]): EgressRecord[] {
  const hidden = { PERSON: 1, PHONE: 1 };
  const added = purposes.map((purpose) => ({
    at: new Date().toISOString(),
    caught: 0,
    chars: draft.brief.length + draft.body.length,
    hidden,
    provider: "gemini" as const,
    purpose,
  }));
  return [...(draft.egress ?? []), ...added];
}

function refusal(status: number, code: ApiErrorCode, endpoint: string): never {
  throw new ApiError(status, code, endpoint);
}

/** A typed instruction has no prepared answer; only the suggestions under the box do. */
function refinedBody({ json, endpoint }: Call): string {
  const instruction = String(json.instruction ?? "").trim();
  if (SUGGESTED.direct.has(instruction)) return DEMO_COMPOSE_REFINED.direct;
  if (SUGGESTED.deadline.has(instruction)) return DEMO_COMPOSE_REFINED.deadline;
  return refusal(INVALID, ApiErrorCode.DemoSuggestionsOnly, endpoint);
}

/** Drafts newest first, then sent, built as the dashboard updates its own copy of the list. */
const composeList = (): ComposeList => state.composeDrafts.reduce(withDraft, EMPTY_COMPOSE_LIST);

function newDraft({ json }: Call): ComposeDraft {
  const now = new Date().toISOString();
  const draft: ComposeDraft = {
    id: `demo-compose-${state.composeDrafts.length + 1}-${Date.now()}`,
    to: [],
    cc: [],
    subject: "",
    brief: "",
    body: "",
    tone: "professional",
    state: ComposeState.Draft,
    sources: [],
    reviewReasons: [],
    details: DEMO_COMPOSE_DETAILS,
    egress: [],
    updatedAt: now,
  };
  state.composeDrafts.push(apply(draft, json));
  return draft;
}

function write(call: Call): ComposeDraft {
  const draft = apply(editableDraft(call), call.json);
  if (!draft.brief.trim()) refusal(INVALID, ApiErrorCode.Empty, call.endpoint);
  Object.assign(draft, {
    subject: draft.subject.trim() ? draft.subject : DEMO_COMPOSE_WRITTEN.subject,
    body: DEMO_COMPOSE_WRITTEN.body,
    sources: DEMO_COMPOSE_SOURCES,
    criticConfidence: DEMO_CONFIDENCE,
    reviewReasons: [],
    generatedAt: new Date().toISOString(),
  });
  draft.egress = aiSteps(draft, "search", "draft", "critic");
  record("compose_written", {
    draft: draft.id,
    sources: DEMO_COMPOSE_SOURCES.length,
    review: false,
  });
  return draft;
}

function refine(call: Call): ComposeDraft {
  const draft = apply(editableDraft(call), call.json);
  if (!draft.body.trim()) refusal(INVALID, ApiErrorCode.Empty, call.endpoint);
  draft.body = refinedBody(call);
  draft.egress = aiSteps(draft, "refine", "critic");
  record("compose_refined", { draft: draft.id, review: false });
  return draft;
}

/** The backend's checks, in its order, before anything is claimed (backend/app/compose.py). */
function refusedSend(email: ComposeDraft): ApiErrorCode | null {
  const text = `${email.subject}\n${email.body}`;
  if (email.to.length === 0) return ApiErrorCode.NoRecipients;
  if (!email.subject.trim()) return ApiErrorCode.NoSubject;
  if (!email.body.trim()) return ApiErrorCode.Empty;
  if (hasMissingDetails(text, detailValues(email.details))) {
    return ApiErrorCode.UnresolvedPlaceholders;
  }
  if (findRedactionMarkers(restoreDetails(text, detailValues(email.details))).length > 0) {
    return ApiErrorCode.RedactionMarkers;
  }
  return null;
}

/** Pretend, like every send in the demo: the draft is marked sent and nothing goes anywhere. */
function send(call: Call): ComposeDraft {
  const found = findDraft(call);
  // Sending what was sent answers with it, as the backend does, rather than refusing.
  if (found.state === ComposeState.Sent) return found;
  const draft = editableDraft(call);
  const email = apply(structuredClone(draft), call.json);
  const refused = refusedSend(email);
  if (refused) refusal(INVALID, refused, call.endpoint);
  const sentAt = new Date().toISOString();
  Object.assign(draft, email, { state: ComposeState.Sent, sentAt, updatedAt: sentAt });
  record("compose_sent", {
    draft: draft.id,
    recipients: draft.to.length + draft.cc.length,
    restored: draft.details?.length ?? 0,
  });
  return draft;
}

/** The demo never loses track of a send, so there is never an outcome to settle. */
function settle(call: Call): ComposeDraft {
  const draft = findDraft(call);
  if (draft.state !== ComposeState.OutcomeUnknown) {
    refusal(CONFLICT, ApiErrorCode.Conflict, call.endpoint);
  }
  return draft;
}

function remove(call: Call): void {
  const draft = findDraft(call);
  if (draft.state === ComposeState.Sending || draft.state === ComposeState.OutcomeUnknown) {
    refusal(CONFLICT, ApiErrorCode.SendInProgress, call.endpoint);
  }
  state.composeDrafts = state.composeDrafts.filter((other) => other.id !== draft.id);
  record("compose_deleted", { draft: draft.id, was_sent: draft.state === ComposeState.Sent });
}

export const COMPOSE_ROUTES: Route[] = [
  { method: "GET", pattern: /^\/compose$/, handler: composeList },
  { method: "POST", pattern: /^\/compose$/, handler: newDraft },
  { method: "GET", pattern: /^\/compose\/([^/]+)$/, handler: findDraft },
  {
    method: "PATCH",
    pattern: /^\/compose\/([^/]+)$/,
    handler: (call) => apply(editableDraft(call), call.json),
  },
  { method: "DELETE", pattern: /^\/compose\/([^/]+)$/, handler: remove },
  { method: "POST", pattern: /^\/compose\/([^/]+)\/write$/, thinks: true, handler: write },
  { method: "POST", pattern: /^\/compose\/([^/]+)\/refine$/, thinks: true, handler: refine },
  { method: "POST", pattern: /^\/compose\/([^/]+)\/send$/, handler: send },
  { method: "POST", pattern: /^\/compose\/([^/]+)\/outcome$/, handler: settle },
];
