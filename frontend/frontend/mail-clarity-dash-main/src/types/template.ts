/** Saved reply templates (specs/features/reply-templates.md). */
import type { Language } from "../lib/preferences";
import type { Schemas, WithEnums } from "./schema";

/** What the reader writes: title, text with {{variables}}, language and trigger words. */
export type TemplateDraft = WithEnums<Schemas["TemplateBody"], { language: Language }>;

export type Template = WithEnums<Schemas["TemplateView"], { language: Language }>;
