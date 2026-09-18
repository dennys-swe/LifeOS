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
  const { refresh, payables } = useFinance();
  onRefreshSeen(refresh);
  return (
    <ul>
      {payables.map((p) => (
        <li key={p.id}>{p.title}</li>
      ))}
    </ul>
  );
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

  it("dado cacheado além do TTL revalida em segundo plano ao ser usado", async () => {
    const oldFetchedAt = Date.now() - 10 * 60 * 1000; // 10 min — além do TTL de 3 min
    sessionStorage.setItem(
      "lifeos-finance-cache-v1",
      JSON.stringify({
        "1-2026": { payables: [], categories: [], summary: {}, fetchedAt: oldFetchedAt },
      })
    );

    render(<Harness onRefreshSeen={() => {}} />);

    await act(async () => {});
    // usa o cache na hora, mas por estar velho dispara a revalidação silenciosa
    expect(api.get).toHaveBeenCalledTimes(3);
  });

  it("entrada de cache sem fetchedAt (formato de antes desta mudança) é tratada como velha", async () => {
    sessionStorage.setItem(
      "lifeos-finance-cache-v1",
      JSON.stringify({ "1-2026": { payables: [], categories: [], summary: {} } })
    );

    render(<Harness onRefreshSeen={() => {}} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3);
  });

  it("revalida em segundo plano ao voltar o foco da aba com cache velho", async () => {
    render(<Harness onRefreshSeen={() => {}} />);
    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3);

    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(api.get).toHaveBeenCalledTimes(6);
    vi.useRealTimers();
  });

  it("não revalida em foco quando o cache ainda está fresco", async () => {
    render(<Harness onRefreshSeen={() => {}} />);
    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(api.get).toHaveBeenCalledTimes(3);
  });

  it("visibilitychange e focus disparando juntos revalidam só uma vez", async () => {
    render(<Harness onRefreshSeen={() => {}} />);
    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3);

    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    // navegadores tipicamente disparam os dois eventos ao voltar pra aba
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });

    // 3 da carga inicial + 3 de UMA revalidação (não 3+6=9, que seria duas)
    expect(api.get).toHaveBeenCalledTimes(6);
    vi.useRealTimers();
  });

  it("resposta atrasada de um mês antigo não sobrescreve o mês pro qual o usuário já trocou", async () => {
    let resolveJaneiro;
    const janeiroPending = new Promise((resolve) => {
      resolveJaneiro = resolve;
    });

    api.get.mockImplementation((path, config) => {
      const m = config?.params?.month;
      if (path === "/payables" && m === 1) {
        return janeiroPending.then(() => ({ data: [{ id: "jan", title: "Aluguel Janeiro" }] }));
      }
      if (path === "/payables" && m === 2) {
        return Promise.resolve({ data: [{ id: "fev", title: "Aluguel Fevereiro" }] });
      }
      if (path === "/categories") return Promise.resolve({ data: [] });
      if (path === "/summary") return Promise.resolve({ data: {} });
      return Promise.reject(new Error(`unexpected ${path} month=${m}`));
    });

    render(<Harness onRefreshSeen={() => {}} />);

    // janeiro fica pendurado (nunca resolvido ainda) enquanto o usuário troca
    // pra fevereiro, que resolve na hora.
    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    expect(await screen.findByText("Aluguel Fevereiro")).toBeTruthy();

    // agora a resposta atrasada de janeiro finalmente chega
    await act(async () => {
      resolveJaneiro();
      await janeiroPending;
    });

    // não pode ter sobrescrito a tela, que deve continuar mostrando fevereiro
    expect(screen.queryByText("Aluguel Janeiro")).toBeNull();
    expect(screen.getByText("Aluguel Fevereiro")).toBeTruthy();
  });
});
