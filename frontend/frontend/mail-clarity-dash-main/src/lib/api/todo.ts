import type { FollowUpDraft, Todo } from "../../types/todo";
import { HttpMethod, request } from "./client";

export const fetchTodo = () => request<Todo>("/todo");

/** No reply needed: out of the to-do lists, still in the inbox. */
export const dismissEmail = (emailId: string) =>
  request<void>(`/emails/${encodeURIComponent(emailId)}/dismiss`, { method: HttpMethod.Post });

/** Not waiting: the reply leaves the waiting list. */
export const notWaiting = (sentId: string) =>
  request<void>(`/todo/waiting/${encodeURIComponent(sentId)}/dismiss`, { method: HttpMethod.Post });

/** A follow-up to an unanswered reply sent through AIMail, in placeholder form like any draft. */
export const draftFollowUp = (sentId: string) =>
  request<FollowUpDraft>(`/todo/waiting/${encodeURIComponent(sentId)}/follow-up`, {
    method: HttpMethod.Post,
  });

export const sendFollowUp = ({ sentId, draft }: { sentId: string; draft: string }) =>
  request<void>(`/todo/waiting/${encodeURIComponent(sentId)}/follow-up/send`, {
    method: HttpMethod.Post,
    json: { draft },
  });

export const saveWaitingDays = (waitingDays: number) =>
  request<{ waitingDays: number }>("/settings/todo", {
    method: HttpMethod.Put,
    json: { waitingDays },
  });
