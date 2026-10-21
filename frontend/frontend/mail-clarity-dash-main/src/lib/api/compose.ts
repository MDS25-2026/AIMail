import type {
  ComposeDraft,
  ComposeFields,
  ComposeList,
  OutgoingEmail,
  SettleOutcome,
} from "../../types/compose";
import { HttpMethod, request } from "./client";

const draftPath = (id: string, action = "") => `/compose/${encodeURIComponent(id)}${action}`;

/** What the user typed; a field left out keeps what is stored. */
export type ComposeChange = { id: string; fields?: Partial<ComposeFields> };

/** The user's unsent drafts and recently sent new emails, newest first. */
export const fetchComposeList = () => request<ComposeList>("/compose");

export const fetchComposeDraft = (id: string) => request<ComposeDraft>(draftPath(id));

export const createComposeDraft = (fields: Partial<ComposeFields> = {}) =>
  request<ComposeDraft>("/compose", { method: HttpMethod.Post, json: fields });

/** Autosave; refused once the email is being sent or was sent. */
export const saveComposeDraft = ({ id, fields }: ComposeChange) =>
  request<ComposeDraft>(draftPath(id), { method: HttpMethod.Patch, json: fields });

export const deleteComposeDraft = (id: string) =>
  request<void>(draftPath(id), { method: HttpMethod.Delete });

/** The model writes the body (and a subject, if none was typed) from the brief; takes seconds. */
export const writeComposeDraft = ({ id, fields }: ComposeChange) =>
  request<ComposeDraft>(draftPath(id, "/write"), { method: HttpMethod.Post, json: fields });

export const refineComposeDraft = ({
  id,
  fields,
  instruction,
}: ComposeChange & { instruction: string }) =>
  request<ComposeDraft>(draftPath(id, "/refine"), {
    method: HttpMethod.Post,
    json: { ...fields, instruction },
  });

export const sendComposeDraft = ({ id, email }: { id: string; email: OutgoingEmail }) =>
  request<ComposeDraft>(draftPath(id, "/send"), { method: HttpMethod.Post, json: email });

/** The user checked Gmail's Sent folder after an unknown outcome. */
export const settleComposeOutcome = ({ id, outcome }: { id: string; outcome: SettleOutcome }) =>
  request<ComposeDraft>(draftPath(id, "/outcome"), {
    method: HttpMethod.Post,
    json: { outcome },
  });
