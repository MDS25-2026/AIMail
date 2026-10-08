import type { Language } from "../lib/preferences";
import { assertSameValues, type Schemas, type WithEnums } from "./schema";

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

export type StyleExample = WithEnums<Schemas["ExampleView"], { source: ExampleSource }>;

export type StyleHabit = WithEnums<
  Schemas["HabitView"],
  { kind: StyleHabitKind; language?: Language | null }
>;

export type WritingStyle = WithEnums<
  Schemas["WritingStyleView"],
  { examples: StyleExample[]; habits: StyleHabit[] }
>;

assertSameValues<`${ExampleSource}`, Schemas["ExampleSource"]>(true);
assertSameValues<`${Language}`, Schemas["Language"]>(true);
