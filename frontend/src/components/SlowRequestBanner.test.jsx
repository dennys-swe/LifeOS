import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useSlowRequestBanner } from "../hooks/useSlowRequestBanner";
import SlowRequestBanner from "./SlowRequestBanner";

vi.mock("../hooks/useSlowRequestBanner", () => ({
  useSlowRequestBanner: vi.fn(),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("SlowRequestBanner", () => {
  it("não renderiza nada quando não está lento", () => {
    useSlowRequestBanner.mockReturnValue(false);
    const { container } = render(<SlowRequestBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("mostra o aviso de aquecimento quando está lento", () => {
    useSlowRequestBanner.mockReturnValue(true);
    const { getByText } = render(<SlowRequestBanner />);
    expect(getByText(/Aquecendo o servidor/)).toBeTruthy();
  });
});
