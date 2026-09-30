import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../services/api";
import DataQualityBanner from "./DataQualityBanner";

vi.mock("../../services/api", () => ({ default: { get: vi.fn() } }));

const summary = (over = {}) => ({
  open_total: 3,
  by_severity: { high: 0, warn: 2, info: 1 },
  by_kind: {},
  last_detected_at: "2026-10-01T10:00:00",
  ...over,
});

function renderBanner() {
  return render(
    <MemoryRouter>
      <DataQualityBanner />
    </MemoryRouter>
  );
}

async function settle() {
  await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
  await new Promise((r) => setTimeout(r, 0));
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DataQualityBanner (#200)", () => {
  it("mostra a contagem e leva para a tela", async () => {
    api.get.mockResolvedValue({ data: summary() });
    renderBanner();

    const banner = await screen.findByTestId("data-quality-banner");
    expect(banner.textContent).toContain("3 possíveis erros nos seus dados");
    expect(banner.getAttribute("href")).toBe("/data-quality");
    expect(api.get).toHaveBeenCalledWith("/data-quality/summary");
  });

  it("destaca quando há avisos que pedem atenção", async () => {
    api.get.mockResolvedValue({
      data: summary({ open_total: 4, by_severity: { high: 2, warn: 1, info: 1 } }),
    });
    renderBanner();

    const banner = await screen.findByTestId("data-quality-banner");
    expect(banner.textContent).toContain("2 pedem atenção");
    expect(banner.className).toContain("rose");
  });

  it("usa tom neutro quando nada é urgente", async () => {
    api.get.mockResolvedValue({ data: summary() });
    renderBanner();

    const banner = await screen.findByTestId("data-quality-banner");
    expect(banner.textContent).not.toContain("pedem atenção");
    expect(banner.className).toContain("amber");
  });

  it("usa o singular com um aviso só", async () => {
    api.get.mockResolvedValue({ data: summary({ open_total: 1, by_severity: { high: 0, warn: 0, info: 1 } }) });
    renderBanner();

    expect((await screen.findByTestId("data-quality-banner")).textContent).toContain(
      "1 possível erro nos seus dados"
    );
  });

  it("não aparece sem avisos abertos", async () => {
    api.get.mockResolvedValue({ data: summary({ open_total: 0, by_severity: { high: 0, warn: 0, info: 0 } }) });
    renderBanner();

    await settle();
    expect(screen.queryByTestId("data-quality-banner")).toBeNull();
  });

  it("falha em silêncio se a API não responder", async () => {
    api.get.mockRejectedValue(new Error("fora do ar"));
    renderBanner();

    await settle();
    expect(screen.queryByTestId("data-quality-banner")).toBeNull();
  });
});
