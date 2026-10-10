/** To-do (specs/features/todo-page.md). */
import type { Email } from "./email";
import type { Schemas, WithEnums } from "./schema";

export type TodoSection = WithEnums<Schemas["TodoSection"], { emails: Email[] }>;

export type WaitingReply = WithEnums<Schemas["WaitingReply"], { email: Email | null }>;

export type Todo = WithEnums<
  Schemas["Todo"],
  {
    needsAction: TodoSection;
    needsReview: TodoSection;
    unsentDrafts: TodoSection;
    waiting: WaitingReply[];
  }
>;

/** A follow-up draft in placeholder form, with the details of the thread it is numbered in. */
export type FollowUpDraft = Schemas["FollowUpDraft"];
