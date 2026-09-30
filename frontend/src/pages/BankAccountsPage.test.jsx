import { act, render } from "@testing-library/react";
import { StrictMode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../services/api";
import { FinanceProvider } from "../context/FinanceContext";
import BankAccountsPage from "./BankAccountsPage";

vi.mock("../services/api", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

function mockApiResponses() {
  api.get.mockImplementation((path) => {
    if (path === "/bank-accounts") return Promise.resolve({ data: [] });
    if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
}

function renderPage() {
  return render(
    <FinanceProvider month={1} year={2026}>
      <BankAccountsPage />
    </FinanceProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  mockApiResponses();
});

describe("BankAccountsPage — revalidação por staleness (issue #116)", () => {
  it("busca as contas uma vez ao montar", async () => {
    renderPage();
    await act(async () => {});

    expect(api.get).toHaveBeenCalledWith("/bank-accounts");
    expect(api.get).toHaveBeenCalledWith("/bank-accounts/reconciliation-suggestions");
  });

  it("revalida em segundo plano ao voltar o foco da aba com dado velho", async () => {
    vi.useFakeTimers();
    renderPage();
    await act(async () => {});

    const callsBefore = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
    expect(callsBefore).toBe(1);

    vi.setSystemTime(Date.now() + 10 * 60 * 1000); // além do TTL de 3min

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    const callsAfter = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
    expect(callsAfter).toBe(2);

    vi.useRealTimers();
  });

  it("revalidação automática não anima/desabilita o botão 'Atualizar Conexões' (é silenciosa de verdade)", async () => {
    vi.useFakeTimers();
    let resolveAutoRevalidation;
    let callCount = 0;
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        callCount += 1;
        if (callCount === 2) {
          return new Promise((resolve) => {
            resolveAutoRevalidation = () => resolve({ data: [] });
          });
        }
        return Promise.resolve({ data: [] });
      }
      if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    const { getByText } = renderPage();
    await act(async () => {});

    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // revalidação automática em andamento (2ª chamada ainda pendurada) —
    // o botão não pode ficar desabilitado/girando por causa dela.
    const button = getByText("Atualizar Conexões").closest("button");
    expect(button.disabled).toBe(false);

    await act(async () => {
      resolveAutoRevalidation();
    });

    vi.useRealTimers();
  });

  it("não revalida em foco quando o dado ainda está fresco", async () => {
    renderPage();
    await act(async () => {});

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    const calls = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
    expect(calls).toBe(1);
  });

  it("visibilitychange e focus disparando juntos revalidam só uma vez (sem chamada duplicada em andamento)", async () => {
    vi.useFakeTimers();
    renderPage();
    await act(async () => {});

    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });

    // O dedup mora no hook (useRevalidateOnFocus), não em load() — a 2ª
    // chamada síncrona (focus logo após visibilitychange) não dispara outra
    // rodada de fetch em cima da 1ª revalidação automática ainda em andamento.
    const calls = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
    expect(calls).toBe(2); // 1 do mount + 1 da revalidação (não 3)

    vi.useRealTimers();
  });

  it("uma mutação (sincronizar) não é engolida por uma revalidação automática em andamento", async () => {
    // Achado no code-review: um guard de "já está carregando" dentro do
    // próprio load() bloquearia esta chamada manual (pós-sync) se ela caísse
    // no meio de uma revalidação automática em andamento — a tela ficaria
    // com dado pré-sync até a próxima revalidação, minutos depois. O dedup
    // certo é só entre as duas chamadas AUTOMÁTICAS (visibilitychange+focus),
    // nunca bloqueando um load() disparado por ação do usuário.
    vi.useFakeTimers();
    let resolveAutoRevalidation;
    let callCount = 0;
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        callCount += 1;
        if (callCount === 2) {
          return new Promise((resolve) => {
            resolveAutoRevalidation = () => resolve({ data: [{ id: "a1", name: "Conta" }] });
          });
        }
        // 3ª chamada (a manual, pós-sync) resolve na hora com dado novo.
        if (callCount === 3) {
          return Promise.resolve({ data: [{ id: "a1", name: "Conta Pós-Sync" }] });
        }
        return Promise.resolve({ data: [{ id: "a1", name: "Conta" }] });
      }
      if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
      if (path === "/bank-accounts/a1/cards") return Promise.resolve({ data: [] });
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
    api.post.mockResolvedValue({ data: { sync_status: "SYNCING" } });

    const { getByText } = renderPage();
    await act(async () => {});

    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    // dispara a revalidação automática — fica pendurada na 2ª chamada
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // enquanto isso, o usuário clica em Sincronizar — dispara a 3ª chamada,
    // que resolve ANTES da 2ª (a automática, ainda pendurada)
    await act(async () => {
      getByText("Sincronizar").click();
    });

    expect(getByText("Conta Pós-Sync")).toBeTruthy();

    // agora resolve a revalidação automática (mais VELHA, mas terminando
    // DEPOIS) — não pode reverter a tela pro dado pré-sync
    await act(async () => {
      resolveAutoRevalidation();
    });

    const totalCalls = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
    expect(totalCalls).toBe(3); // 1 (mount) + 1 (auto) + 1 (manual pós-sync)
    expect(getByText("Conta Pós-Sync")).toBeTruthy();

    vi.useRealTimers();
  });

  it("continua carregando dados depois do ciclo montagem→limpeza→montagem do StrictMode (dev)", async () => {
    // Achado no code-review: `mountedRef` só virava `false` na limpeza e
    // nunca voltava a `true` — o StrictMode do modo dev roda esse ciclo de
    // propósito em toda montagem, então `load()` ficava travado (`if
    // (!mountedRef.current) return`) silenciosamente pra sempre em
    // `npm run dev`. Nunca afetou produção (que não double-invoca efeitos).
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        return Promise.resolve({ data: [{ id: "a1", name: "Conta StrictMode" }] });
      }
      if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
      if (path === "/bank-accounts/a1/cards") return Promise.resolve({ data: [] });
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    const { getByText } = render(
      <StrictMode>
        <FinanceProvider month={1} year={2026}>
          <BankAccountsPage />
        </FinanceProvider>
      </StrictMode>
    );
    await act(async () => {});

    expect(getByText("Conta StrictMode")).toBeTruthy();
  });

  it("loading não fica travado pra sempre quando uma chamada manual perde a corrida pra uma revalidação silenciosa mais nova", async () => {
    // Achado no code-review: gatear `setLoading(false)` por `seq ===
    // requestSeqRef.current` deixava o spinner travado em `true` pra sempre
    // quando a chamada vencedora (mais nova) era silenciosa — ela nunca
    // mexe em `loading`, e a perdedora (não-silenciosa, quem ligou o
    // spinner) não passava mais no `seq ===`, então ninguém desligava.
    vi.useFakeTimers();
    let resolveManual;
    let callCount = 0;
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        callCount += 1;
        if (callCount === 2) {
          // chamada manual (clique em "Atualizar Conexões") — fica pendurada
          return new Promise((resolve) => {
            resolveManual = () => resolve({ data: [] });
          });
        }
        return Promise.resolve({ data: [] });
      }
      if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    const { getByText } = renderPage();
    await act(async () => {});

    await act(async () => {
      getByText("Atualizar Conexões").click();
    });

    let button = getByText("Atualizar Conexões").closest("button");
    expect(button.disabled).toBe(true); // chamada manual em andamento

    // a revalidação silenciosa dispara e VENCE a corrida (resolve antes da manual)
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    // só agora a manual (perdedora) resolve
    await act(async () => {
      resolveManual();
    });

    button = getByText("Atualizar Conexões").closest("button");
    expect(button.disabled).toBe(false); // sem o fix, ficava travado em true

    vi.useRealTimers();
  });

  it("duas chamadas não-silenciosas sobrepostas só desligam o spinner quando a mais nova termina", async () => {
    // Achado no code-review: gatear `setLoading(false)` só por `!silent`
    // (sem contar quantas chamadas não-silenciosas estão em andamento)
    // deixava a 1ª chamada desligar o spinner assim que ELA terminasse,
    // mesmo com uma 2ª (mais nova) ainda buscando — o botão reaparecia
    // habilitado com um fetch de verdade ainda pendente.
    let resolveSecond;
    let callCount = 0;
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        callCount += 1;
        if (callCount === 1) return Promise.resolve({ data: [] }); // mount
        if (callCount === 2) return Promise.resolve({ data: [] }); // 1ª manual, resolve rápido
        return new Promise((resolve) => {
          resolveSecond = () => resolve({ data: [] });
        }); // 2ª manual, fica pendurada
      }
      if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });

    const { getByText } = renderPage();
    await act(async () => {});

    // duas chamadas manuais quase simultâneas — a 1ª já resolveu, a 2ª ainda não
    await act(async () => {
      getByText("Atualizar Conexões").click();
      getByText("Atualizar Conexões").click();
    });

    let button = getByText("Atualizar Conexões").closest("button");
    expect(button.disabled).toBe(true); // a 2ª ainda está em andamento

    await act(async () => {
      resolveSecond();
    });

    button = getByText("Atualizar Conexões").closest("button");
    expect(button.disabled).toBe(false);
  });
});

describe("BankAccountsPage — idade real do dado (issue #214)", () => {
  const baseAccount = {
    id: "acc-1",
    name: "Inter + Cartão",
    bank_name: "MeuPluggy",
    account_type: "checking",
    last_sync_at: "2026-09-30T16:38:51Z",
  };

  function mockWithAccount(freshness) {
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        return Promise.resolve({ data: [{ ...baseAccount, freshness }] });
      }
      if (path === "/bank-accounts/reconciliation-suggestions") return Promise.resolve({ data: [] });
      if (path === "/bank-accounts/acc-1/cards") return Promise.resolve({ data: [] });
      return Promise.reject(new Error(`unexpected GET ${path}`));
    });
  }

  it("avisa que a conexão parou de atualizar mesmo com leitura recente do LifeOS", async () => {
    mockWithAccount({
      state: "stale",
      reason: "no_auto_sync",
      data_age_hours: 312,
      auto_sync_scheduled: false,
      consent_days_left: 300,
      consent_expiring: false,
    });
    const { findByTestId, getByText } = renderPage();

    const box = await findByTestId("connection-freshness");
    expect(box.textContent).toContain("Desatualizada");
    expect(box.textContent).toContain("Sem atualização há 13 dias");
    expect(box.textContent).toContain("não está atualizando sozinho");
    expect(getByText(/Lido pelo LifeOS/)).toBeTruthy();
  });

  it("mostra conexão atualizada em horas", async () => {
    mockWithAccount({
      state: "fresh",
      reason: "ok",
      data_age_hours: 10,
      auto_sync_scheduled: true,
      consent_days_left: 300,
      consent_expiring: false,
    });
    const { findByTestId } = renderPage();

    const box = await findByTestId("connection-freshness");
    expect(box.textContent).toContain("Atualizada");
    expect(box.textContent).toContain("há 10 h");
    expect(box.textContent).not.toContain("vence em");
  });

  it("pede reconexão quando o banco precisa de atenção", async () => {
    mockWithAccount({
      state: "attention",
      reason: "needs_attention",
      data_age_hours: 5,
      auto_sync_scheduled: false,
      consent_days_left: 300,
      consent_expiring: false,
    });
    const { findByTestId } = renderPage();

    const box = await findByTestId("connection-freshness");
    expect(box.textContent).toContain("Precisa de atenção");
    expect(box.textContent).toContain("Reconecte");
  });

  it("avisa autorização perto de vencer e já vencida", async () => {
    mockWithAccount({
      state: "fresh",
      reason: "ok",
      data_age_hours: 2,
      auto_sync_scheduled: true,
      consent_days_left: 12,
      consent_expiring: true,
    });
    const first = renderPage();
    expect((await first.findByTestId("connection-freshness")).textContent).toContain("vence em 12 dias");
    first.unmount();

    mockWithAccount({
      state: "fresh",
      reason: "ok",
      data_age_hours: 2,
      auto_sync_scheduled: true,
      consent_days_left: -3,
      consent_expiring: true,
    });
    const second = renderPage();
    expect((await second.findByTestId("connection-freshness")).textContent).toContain("autorização do banco venceu");
  });

  it("mostra estado neutro antes da primeira leitura do item", async () => {
    mockWithAccount({
      state: "unknown",
      reason: "not_checked",
      data_age_hours: null,
      auto_sync_scheduled: false,
      consent_days_left: null,
      consent_expiring: false,
    });
    const { findByTestId } = renderPage();

    expect((await findByTestId("connection-freshness")).textContent).toContain("Sem informação");
  });

  it("não quebra com conta sem o objeto de frescor (resposta antiga)", async () => {
    mockWithAccount(undefined);
    const { findByText, queryByTestId } = renderPage();

    await findByText("Inter + Cartão");
    expect(queryByTestId("connection-freshness")).toBeNull();
  });
});
