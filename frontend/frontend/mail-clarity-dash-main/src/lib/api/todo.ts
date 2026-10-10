import type { Todo } from "../../types/todo";
import { HttpMethod, request } from "./client";

export const fetchTodo = () => request<Todo>("/todo");

/** No reply needed: out of the to-do lists, still in the inbox. */
export const dismissEmail = (emailId: string) =>
  request<void>(`/emails/${encodeURIComponent(emailId)}/dismiss`, { method: HttpMethod.Post });

/** Not waiting: the reply leaves the waiting list. */
export const notWaiting = (sentId: string) =>
  request<void>(`/todo/waiting/${encodeURIComponent(sentId)}/dismiss`, { method: HttpMethod.Post });

export const saveWaitingDays = (waitingDays: number) =>
  request<{ waitingDays: number }>("/settings/todo", {
    method: HttpMethod.Put,
    json: { waitingDays },
  });
