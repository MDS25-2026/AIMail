/**
 * Every cache key, in one factory: an invalidation after a mutation can never miss an entry
 * because of a typo'd key. Only the hooks in this folder use it.
 */
export const queryKeys = {
  session: ["session"] as const,
  emails: ["emails"] as const,
  email: (id: string) => ["email", id] as const,
  emailByThread: (threadId: string) => ["email-by-thread", threadId] as const,
  translation: (id: string, language: string) => ["translation", id, language] as const,
  documents: ["documents"] as const,
  systemInfo: ["system-info"] as const,
  holdingReplySettings: ["holding-reply-settings"] as const,
  holdingReplies: ["holding-replies"] as const,
  privateMode: ["private-mode"] as const,
  writingStyle: ["writing-style"] as const,
  auditTrail: ["audit-trail"] as const,
  admin: {
    all: ["admin"] as const,
    session: ["admin", "session"] as const,
    overview: (days: number) => ["admin", "overview", days] as const,
    flagged: ["admin", "flagged"] as const,
    audit: (failuresOnly: boolean) => ["admin", "audit", failuresOnly] as const,
  },
};
