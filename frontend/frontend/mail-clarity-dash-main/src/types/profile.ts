/** Writing style (specs/features/writing-profile.md). Every text is the masked copy that was stored. */

export enum StyleHabitKind {
  Greeting = "greeting",
  Signoff = "signoff",
  Length = "length",
  Swap = "swap",
}

export enum ExampleSource {
  Pasted = "pasted",
  Sent = "sent",
}

/** The values a `length` habit can carry. */
export enum ReplyLength {
  Short = "short",
  Medium = "medium",
  Long = "long",
}

export type StyleExample = { id: string; text: string; source: ExampleSource; createdAt: string };

export type StyleHabit = {
  id: string;
  kind: StyleHabitKind;
  value: string;
  evidence: number;
  outOf: number;
};

export type WritingStyle = {
  description: string;
  learning: boolean;
  examples: StyleExample[];
  habits: StyleHabit[];
  maxExamples: number;
};
