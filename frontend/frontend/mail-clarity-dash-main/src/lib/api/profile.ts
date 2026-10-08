import type { WritingStyle } from "../../types/profile";
import { HttpMethod, request } from "./client";

const WRITING = "/profile/writing";

export const fetchWritingStyle = () => request<WritingStyle>(WRITING);

export const saveStyleDescription = (description: string) =>
  request<WritingStyle>(`${WRITING}/description`, {
    method: HttpMethod.Put,
    json: { description },
  });

export const setStyleLearning = (enabled: boolean) =>
  request<WritingStyle>(`${WRITING}/learning`, { method: HttpMethod.Put, json: { enabled } });

/** A pasted text, or a sent reply by its email id; the server masks either before storing it. */
export const addStyleExample = (source: { text: string } | { emailId: string }) =>
  request<WritingStyle>(`${WRITING}/examples`, { method: HttpMethod.Post, json: source });

export const deleteStyleExample = (id: string) =>
  request<void>(`${WRITING}/examples/${encodeURIComponent(id)}`, { method: HttpMethod.Delete });

export const hideStyleHabit = (id: string) =>
  request<void>(`${WRITING}/habits/${encodeURIComponent(id)}`, { method: HttpMethod.Delete });

export const deleteWritingStyle = () => request<void>(WRITING, { method: HttpMethod.Delete });
