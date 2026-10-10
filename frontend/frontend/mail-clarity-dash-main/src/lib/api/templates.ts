import type { Email, Tone } from "../../types/email";
import type { Language } from "../preferences";
import type { Template, TemplateDraft } from "../../types/template";
import { HttpMethod, request } from "./client";

const templatePath = (id: string, action = "") => `/templates/${encodeURIComponent(id)}${action}`;

export const fetchTemplates = () => request<Template[]>("/templates");

export const createTemplate = (draft: TemplateDraft) =>
  request<Template>("/templates", { method: HttpMethod.Post, json: draft });

export const updateTemplate = ({ id, draft }: { id: string; draft: TemplateDraft }) =>
  request<Template>(templatePath(id), { method: HttpMethod.Put, json: draft });

export const deleteTemplate = (id: string) =>
  request<void>(templatePath(id), { method: HttpMethod.Delete });

/** The template filled for one email, placeholders and all; nothing is stored. */
export const fillTemplate = ({ templateId, emailId }: { templateId: string; emailId: string }) =>
  request<{ text: string }>(templatePath(templateId, "/fill"), {
    method: HttpMethod.Post,
    json: { emailId },
  });

/** The agent rewrites the template for the email; returns the email with the stored draft. */
export const adaptTemplate = ({
  templateId,
  emailId,
  tone,
}: {
  templateId: string;
  emailId: string;
  tone: Tone;
}) =>
  request<Email>(templatePath(templateId, "/adapt"), {
    method: HttpMethod.Post,
    json: { emailId, tone },
  });

/** A translated copy to check and save; the original is unchanged. */
export const translateTemplate = ({ id, language }: { id: string; language: Language }) =>
  request<TemplateDraft>(templatePath(id, "/translate"), {
    method: HttpMethod.Post,
    json: { language },
  });
