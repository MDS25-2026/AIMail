/** Masking vocabulary shared with backend/app/core/redaction.py; factories, as /g regexes keep lastIndex. */

// The same kinds as backend/app/core/redaction.py DETAIL_KINDS.
const PLACEHOLDER_SOURCE = String.raw`\[(?:PERSON|EMAIL|PHONE|IC|PASSPORT|ACCOUNT|CARD|LOCATION|ORG)_\d+\]`;
// Mirrors backend/app/core/redaction.py REDACTION_MARKER.
const REDACTION_MARKER_SOURCE = String.raw`\[(?:[A-Z_]+_REDACTED|Redacted|REDACTED)\]|\((?:hidden|name)\)`;
const LEADING_TAG = /^[[(]([A-Za-z]+)/;

export function placeholderPattern(): RegExp {
  return new RegExp(PLACEHOLDER_SOURCE, "g");
}

export function redactionMarkerPattern(): RegExp {
  return new RegExp(REDACTION_MARKER_SOURCE, "g");
}

export function isPlaceholder(text: string): boolean {
  return new RegExp(`^${PLACEHOLDER_SOURCE}$`).test(text);
}

export enum HiddenKind {
  Name = "name",
  Email = "email",
  Phone = "phone",
  Id = "id",
  Account = "account",
  Card = "card",
  Place = "place",
  Organisation = "organisation",
  Other = "other",
}

// Placeholder kinds and redaction-marker words ([IC_REDACTED], (name)) share one map.
const KIND_BY_TAG: Readonly<Record<string, HiddenKind>> = {
  PERSON: HiddenKind.Name,
  NAME: HiddenKind.Name,
  EMAIL: HiddenKind.Email,
  PHONE: HiddenKind.Phone,
  IC: HiddenKind.Id,
  PASSPORT: HiddenKind.Id,
  ACCOUNT: HiddenKind.Account,
  CARD: HiddenKind.Card,
  LOCATION: HiddenKind.Place,
  ORG: HiddenKind.Organisation,
};

/** The kind of detail a placeholder or marker stands for. */
export function kindOf(marker: string): HiddenKind {
  const tag = LEADING_TAG.exec(marker)?.[1]?.toUpperCase() ?? "";
  return KIND_BY_TAG[tag] ?? HiddenKind.Other;
}
