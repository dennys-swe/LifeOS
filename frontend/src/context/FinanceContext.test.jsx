import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../services/api";
import { FinanceProvider, useFinance } from "./FinanceContext";

vi.mock("../services/api", () => ({
  default: { get: vi.fn() },
}));

function mockApiResponses() {
  api.get.mockImplementation((path) => {
    if (path === "/payables") return Promise.resolve({ data: [] });
    if (path === "/categories") return Promise.resolve({ data: [] });
    if (path === "/summary") return Promise.resolve({ data: {} });
    return Promise.reject(new Error(`unexpected path ${path}`));
  });
}

// Componente de teste: guarda a referência de `refresh` a cada render e
// expõe controles pra trocar month/year (simula navegação entre abas) e
// disparar refresh() (simula uma mutação, ex: pagar uma conta).
function Consumer({ onRefreshSeen }) {
  const { refresh } = useFinance();
  onRefreshSeen(refresh);
  return null;
}

function Harness({ onRefreshSeen }) {
  const [month, setMonth] = useState(1);
  const [year] = useState(2026);
  return (
    <FinanceProvider month={month} year={year}>
      <Consumer onRefreshSeen={onRefreshSeen} />
      <button onClick={() => setMonth(2)}>ir para fevereiro</button>
      <button onClick={() => setMonth(1)}>voltar para janeiro</button>
      <RefreshButton />
    </FinanceProvider>
  );
}

function RefreshButton() {
  const { refresh } = useFinance();
  return <button onClick={refresh}>refresh</button>;
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  mockApiResponses();
});

describe("FinanceProvider", () => {
  it("não refaz as 3 chamadas ao voltar para um mês já buscado nesta sessão", async () => {
    const seen = [];
    render(<Harness onRefreshSeen={(fn) => seen.push(fn)} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3); // janeiro

    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    expect(api.get).toHaveBeenCalledTimes(6); // fevereiro, ainda não visto

    await act(async () => {
      screen.getByText("voltar para janeiro").click();
    });
    // janeiro já foi buscado nesta sessão — não deve refazer as 3 chamadas
    expect(api.get).toHaveBeenCalledTimes(6);
  });

  it("refresh() explícito invalida o cache e refaz as 3 chamadas", async () => {
    render(<Harness onRefreshSeen={() => {}} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3);

    await act(async () => {
      screen.getByText("refresh").click();
    });
    expect(api.get).toHaveBeenCalledTimes(6);
  });

  it("refresh tem identidade estável entre renders (issue #66)", async () => {
    const seen = [];
    render(<Harness onRefreshSeen={(fn) => seen.push(fn)} />);

    await act(async () => {});
    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    await act(async () => {
      screen.getByText("voltar para janeiro").click();
    });

    expect(seen.length).toBeGreaterThan(1);
    expect(new Set(seen).size).toBe(1);
  });
});
