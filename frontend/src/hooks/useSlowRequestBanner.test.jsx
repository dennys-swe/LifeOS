import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { shouldShowColdStartBanner } from "../services/api";
import { useSlowRequestBanner } from "./useSlowRequestBanner";

vi.mock("../services/api", () => ({
  shouldShowColdStartBanner: vi.fn(),
}));

function Harness({ onValue }) {
  const slow = useSlowRequestBanner();
  onValue(slow);
  return null;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useSlowRequestBanner", () => {
  it("começa false e vira true quando shouldShowColdStartBanner passa a reportar true", async () => {
    shouldShowColdStartBanner.mockReturnValue(false);
    let latest;
    render(<Harness onValue={(v) => { latest = v; }} />);

    expect(latest).toBe(false);

    shouldShowColdStartBanner.mockReturnValue(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(latest).toBe(true);
  });

  it("volta a false quando shouldShowColdStartBanner volta a reportar false", async () => {
    shouldShowColdStartBanner.mockReturnValue(true);
    let latest;
    render(<Harness onValue={(v) => { latest = v; }} />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(latest).toBe(true);

    shouldShowColdStartBanner.mockReturnValue(false);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(latest).toBe(false);
  });
});
