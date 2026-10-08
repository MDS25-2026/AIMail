/**
 * The backend's response shapes, generated from its OpenAPI schema (make api-types). Types here are
 * derived from them, never copied by hand; a backend change shows up as a compile error, not a runtime undefined.
 */
import type { components } from "../lib/api/schema.gen";

export type Schemas = components["schemas"];

/** A generated shape with some fields swapped for this app's enums (same values, checked below each use). */
export type WithEnums<T, E extends { [K in keyof E]: K extends keyof T ? unknown : never }> = Omit<
  T,
  keyof E
> &
  E;

type Same<A, B> = [A] extends [B] ? ([B] extends [A] ? true : false) : false;

/** Compiles only when an enum's values and the backend's are exactly the same set (drift guard). */
export function assertSameValues<A, B>(_proof: Same<A, B>): void {}
