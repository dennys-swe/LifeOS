import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { describe, expect, it } from "vitest";

import { useMountedRef } from "./useMountedRef";

function Harness({ onRef }) {
  const mountedRef = useMountedRef();
  onRef(mountedRef);
  return null;
}

describe("useMountedRef", () => {
  it("continua true depois do ciclo montagem→limpeza→montagem do StrictMode", () => {
    let ref;
    render(
      <StrictMode>
        <Harness onRef={(r) => { ref = r; }} />
      </StrictMode>
    );

    expect(ref.current).toBe(true);
  });

  it("vira false depois de desmontar de verdade", () => {
    let ref;
    const { unmount } = render(<Harness onRef={(r) => { ref = r; }} />);

    expect(ref.current).toBe(true);
    unmount();
    expect(ref.current).toBe(false);
  });
});
