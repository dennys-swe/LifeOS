import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../../services/api";
import { usageTone } from "../../lib/cardLimits";
import CardLimitsCard from "./CardLimitsCard";

vi.mock("../../services/api", () => ({ default: { get: vi.fn() } }));

const card = (over = {}) => ({
  pluggy_account_id: "c1",
  label: "Nubank Gold",
  status: "ok",
  credit_limit: "1600.00",
  available: "226.86",
  used: "1373.14",
  used_pct: 85.8,
  freshness_state: "fresh",
  ...over,
});

const summary = (over = {}) => ({
  cards: [card()],
  total_limit: "1600.00",
  total_used: "1373.14",
  total_available: "226.86",
  used_pct: 85.8,
  cards_counted: 1,
  cards_ignored: 0,
  cards_without_limit: 0,
  cards_inconsistent: 0,
  freshness_state: "fresh",
  ...over,
});

function renderCard() {
  return render(
    <MemoryRouter>
      <CardLimitsCard />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("usageTone", () => {
  it("separa folga, atenção e aperto", () => {
    expect(usageTone(null)).toBe("slate");
    expect(usageTone(0)).toBe("emerald");
    expect(usageTone(59.9)).toBe("emerald");
    expect(usageTone(60)).toBe("amber");
    expect(usageTone(84.9)).toBe("amber");
    expect(usageTone(85)).toBe("rose");
    expect(usageTone(120)).toBe("rose");
  });
});

describe("CardLimitsCard — limite consolidado (issue #204)", () => {
  it("mostra usado, limite, percentual e disponível", async () => {
    api.get.mockResolvedValue({ data: summary() });
    renderCard();

    const card_ = await screen.findByTestId("card-limits");
    expect(card_.textContent).toContain("1.373,14");
    expect(card_.textContent).toContain("1.600,00");
    expect(card_.textContent).toContain("226,86");
    expect(screen.getByTestId("card-limits-pct").textContent).toContain("85,8% usado");
    expect(api.get).toHaveBeenCalledWith("/cards/limits");
  });

  it("explica que limite usado não é o valor da fatura", async () => {
    api.get.mockResolvedValue({ data: summary() });
    renderCard();

    expect((await screen.findByTestId("card-limits")).textContent).toContain("não é o valor da fatura");
  });

  it("lista cada cartão só quando há mais de um", async () => {
    api.get.mockResolvedValue({ data: summary() });
    const first = renderCard();
    const single = await first.findByTestId("card-limits");
    expect(single.textContent).not.toContain("Nubank Gold");
    first.unmount();

    api.get.mockResolvedValue({
      data: summary({
        cards: [
          card(),
          card({
            pluggy_account_id: "c2",
            label: "Inter",
            credit_limit: "2420.00",
            used: "835.30",
            available: "1584.70",
            used_pct: 34.5,
          }),
        ],
        total_limit: "4020.00",
        total_used: "2208.44",
        total_available: "1811.56",
        used_pct: 54.9,
        cards_counted: 2,
      }),
    });
    const second = renderCard();
    const both = await second.findByTestId("card-limits");
    expect(both.textContent).toContain("Nubank Gold");
    expect(both.textContent).toContain("Inter");
    expect(both.textContent).toContain("34,5%");
  });

  it("não ocupa espaço quando não há cartão com limite", async () => {
    api.get.mockResolvedValue({
      data: summary({ cards: [], cards_counted: 0, total_limit: "0.00", used_pct: null }),
    });
    renderCard();

    await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByTestId("card-limits")).toBeNull();
  });

  it("some sem quebrar se a API falhar", async () => {
    api.get.mockRejectedValue(new Error("boom"));
    renderCard();

    await vi.waitFor(() => expect(api.get).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByTestId("card-limits")).toBeNull();
  });

  it("avisa dado desatualizado e leva para as conexões", async () => {
    api.get.mockResolvedValue({ data: summary({ freshness_state: "stale" }) });
    renderCard();

    const box = await screen.findByTestId("card-limits");
    expect(box.textContent).toContain("desatualizados");
    expect(screen.getByRole("link", { name: "Ver conexões" }).getAttribute("href")).toBe("/banks");
  });

  it("não avisa nada quando está tudo atualizado", async () => {
    api.get.mockResolvedValue({ data: summary() });
    renderCard();

    const box = await screen.findByTestId("card-limits");
    expect(box.textContent).not.toContain("desatualizados");
    expect(screen.queryByRole("link", { name: "Ver conexões" })).toBeNull();
  });

  it("conta os cartões ignorados, sem limite e inconsistentes que ficaram fora da soma", async () => {
    api.get.mockResolvedValue({
      data: summary({ cards_ignored: 1, cards_without_limit: 2, cards_inconsistent: 1 }),
    });
    renderCard();

    const text = (await screen.findByTestId("card-limits")).textContent;
    expect(text).toContain("1 cartão(ões) marcado(s) como ignorado(s)");
    expect(text).toContain("2 cartão(ões) sem limite informado");
    expect(text).toContain("1 cartão(ões) com limite inconsistente");
  });

  it("explica quando nenhum cartão informou o limite", async () => {
    api.get.mockResolvedValue({
      data: summary({ cards: [], cards_counted: 0, cards_without_limit: 1, used_pct: null }),
    });
    renderCard();

    expect((await screen.findByTestId("card-limits")).textContent).toContain(
      "Nenhum cartão informou o limite"
    );
  });
});
