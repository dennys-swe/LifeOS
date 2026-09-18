import { act, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useRevalidateOnFocus } from "./useRevalidateOnFocus";

function Harness({ revalidate }) {
  useRevalidateOnFocus(revalidate);
  return null;
}

describe("useRevalidateOnFocus", () => {
  it("chama revalidate() ao disparar visibilitychange", async () => {
    const revalidate = vi.fn().mockResolvedValue();
    render(<Harness revalidate={revalidate} />);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(revalidate).toHaveBeenCalledTimes(1);
  });

  it("visibilitychange e focus disparando juntos chamam revalidate() só uma vez", async () => {
    let resolveFirst;
    const pending = new Promise((resolve) => { resolveFirst = resolve; });
    const revalidate = vi.fn().mockImplementation(() => pending);

    render(<Harness revalidate={revalidate} />);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });

    expect(revalidate).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveFirst();
    });
  });

  it("uma nova rodada depois que a anterior termina chama revalidate() de novo", async () => {
    const revalidate = vi.fn().mockResolvedValue();
    render(<Harness revalidate={revalidate} />);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(revalidate).toHaveBeenCalledTimes(2);
  });
});
