// @vitest-environment jsdom
import { act } from "@testing-library/react";
import { expect, test } from "vitest";

import { useDemoSwitch } from "../../lib/queries";
import { renderHookWithProviders } from "../../test/render";
import { leaveDemo } from "../mode";
import { record, state } from "../state";

test("each start of the demo is a fresh mailbox, whatever the last visitor did (#236 review)", () => {
  const { result } = renderHookWithProviders(() => useDemoSwitch());
  // The last visitor dismissed an email, pretend-sent one and left a row in the audit trail.
  state.dismissed.set("demo-meeting", new Date().toISOString());
  state.emails[0].sentAt = new Date().toISOString();
  const seeded = state.audit.length;
  record("approve_and_send", { message: state.emails[0].id });

  act(() => result.current.leave());
  act(() => result.current.start());

  expect(state.dismissed.size).toBe(0);
  expect(state.emails[0].sentAt ?? null).toBeNull();
  expect(state.audit).toHaveLength(seeded);
  leaveDemo();
});
