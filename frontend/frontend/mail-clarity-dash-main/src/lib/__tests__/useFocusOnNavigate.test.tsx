// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { useFocusOnNavigate } from "../useFocusOnNavigate";

let pathname = "/";
vi.mock("@tanstack/react-router", () => ({
  useLocation: ({ select }: { select: (location: { pathname: string }) => string }) =>
    select({ pathname }),
}));

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

test("on a page with no content area it gives up after its frames instead of looping", () => {
  vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame"] });
  const frames = vi.spyOn(window, "requestAnimationFrame");
  const { rerender } = renderHook(() => useFocusOnNavigate());
  pathname = "/signin";
  rerender();
  vi.advanceTimersByTime(10_000); // far more than its budget of frames
  const scheduled = frames.mock.calls.length;
  vi.advanceTimersByTime(10_000);
  expect(frames.mock.calls.length).toBe(scheduled); // it stopped
  expect(scheduled).toBeLessThan(100);
});

test("after navigating, the new page's heading takes focus", () => {
  vi.useFakeTimers({ toFake: ["requestAnimationFrame", "cancelAnimationFrame"] });
  pathname = "/";
  const { rerender } = renderHook(() => useFocusOnNavigate());
  document.body.innerHTML = '<div id="main-content"><h1>To-do</h1></div>';
  pathname = "/todo";
  rerender();
  vi.advanceTimersByTime(100);
  expect(document.activeElement?.textContent).toBe("To-do");
});
