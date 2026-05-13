/**
 * Unit tests for the {@link useDebouncedValue} hook.
 */

import * as React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { useDebouncedValue } from "@/lib/use-debounced-value";

function Probe({ value, delay }: { value: string; delay?: number }) {
  const debounced = useDebouncedValue(value, delay);
  return <span data-testid="debounced">{debounced}</span>;
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useDebouncedValue", () => {
  it("returns the initial value immediately on first render", () => {
    const { getByTestId } = render(<Probe value="hello" />);
    expect(getByTestId("debounced").textContent).toBe("hello");
  });

  it("delays propagation of subsequent updates by the configured window", () => {
    const { getByTestId, rerender } = render(<Probe value="a" delay={250} />);
    rerender(<Probe value="ab" delay={250} />);
    rerender(<Probe value="abc" delay={250} />);

    // Before the window elapses the value is still the initial one.
    expect(getByTestId("debounced").textContent).toBe("a");

    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(getByTestId("debounced").textContent).toBe("abc");
  });

  it("uses the supplied delay rather than the default", () => {
    const { getByTestId, rerender } = render(<Probe value="x" delay={500} />);
    rerender(<Probe value="y" delay={500} />);
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(getByTestId("debounced").textContent).toBe("x");
    act(() => {
      vi.advanceTimersByTime(250);
    });
    expect(getByTestId("debounced").textContent).toBe("y");
  });
});
