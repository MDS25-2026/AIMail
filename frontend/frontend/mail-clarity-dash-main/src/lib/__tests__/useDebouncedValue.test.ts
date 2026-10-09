// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useDebouncedValue } from "../useDebouncedValue";

afterEach(() => vi.useRealTimers());

test("only the value the selection stops on comes through", () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 150), {
    initialProps: { value: "a" },
  });
  rerender({ value: "b" });
  act(() => vi.advanceTimersByTime(100));
  rerender({ value: "c" });
  act(() => vi.advanceTimersByTime(100));
  expect(result.current).toBe("a");
  act(() => vi.advanceTimersByTime(60));
  expect(result.current).toBe("c");
});
