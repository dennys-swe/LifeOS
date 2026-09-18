import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../services/api";
import { FinanceProvider } from "../context/FinanceContext";
import { useBankSync } from "./useBankSync";

vi.mock("../services/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

function financeApiResponses() {
  return (path) => {
    if (path === "/payables") return Promise.resolve({ data: [] });
    if (path === "/categories") return Promise.resolve({ data: [] });
    if (path === "/summary") return Promise.resolve({ data: {} });
    return Promise.reject(new Error(`unexpected GET ${path}`));
  };
}

function accountsResponse(accounts) {
  return Promise.resolve({ data: accounts });
}

function Harness({ syncOnMount, onState }) {
  const state = useBankSync({ syncOnMount });
  onState(state);
  return null;
}

function renderHarness({ syncOnMount = false, onState = () => {} } = {}) {
  return render(
    <FinanceProvider month={1} year={2026}>
      <Harness syncOnMount={syncOnMount} onState={onState} />
    </FinanceProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

describe("useBankSync", () => {
  it("dispara sync-all com force=false ao montar quando syncOnMount=true", async () => {
    api.get.mockImplementation(financeApiResponses());
    api.post.mockResolvedValue({ data: { triggered: [] } });

    renderHarness({ syncOnMount: true });
    await act(async () => {});

    expect(api.post).toHaveBeenCalledWith(
      "/bank-accounts/sync-all",
      null,
      { params: { force: false } }
    );
  });

  it("não dispara nada ao montar quando syncOnMount=false", async () => {
    api.get.mockImplementation(financeApiResponses());

    renderHarness({ syncOnMount: false });
    await act(async () => {});

    expect(api.post).not.toHaveBeenCalled();
  });

  it("com contas disparadas, entra em polling e chama refresh() quando todas voltam a IDLE", async () => {
    vi.useFakeTimers();
    let states = [];
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") {
        // 1ª checagem: ainda sincronizando; 2ª: já terminou.
        const call = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
        if (call <= 1) return accountsResponse([{ id: "a1", sync_status: "SYNCING" }]);
        return accountsResponse([{ id: "a1", sync_status: "IDLE" }]);
      }
      return financeApiResponses()(path);
    });
    api.post.mockResolvedValue({ data: { triggered: ["a1"] } });

    renderHarness({ syncOnMount: true, onState: (s) => states.push(s) });
    await act(async () => {});

    expect(states.at(-1).syncing).toBe(true);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(states.at(-1).syncing).toBe(true); // ainda SYNCING na 1ª checagem

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(states.at(-1).syncing).toBe(false); // 2ª checagem: virou IDLE

    // refresh() invalida o cache do FinanceContext — confirma via nova busca
    // de /payables (refetch das 3 chamadas) depois do polling detectar IDLE.
    const payablesCalls = api.get.mock.calls.filter((c) => c[0] === "/payables").length;
    expect(payablesCalls).toBeGreaterThan(1);

    vi.useRealTimers();
  });

  it("não entra em polling quando sync-all não dispara nenhuma conta", async () => {
    vi.useFakeTimers();
    api.get.mockImplementation(financeApiResponses());
    api.post.mockResolvedValue({ data: { triggered: [] } });

    let states = [];
    renderHarness({ syncOnMount: true, onState: (s) => states.push(s) });
    await act(async () => {});

    expect(states.at(-1).syncing).toBe(false);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10000);
    });

    expect(api.get).not.toHaveBeenCalledWith("/bank-accounts");
    vi.useRealTimers();
  });

  it("desiste de pollar depois do teto de tentativas se a conta fica presa em SYNCING", async () => {
    vi.useFakeTimers();
    let states = [];
    api.get.mockImplementation((path) => {
      if (path === "/bank-accounts") return accountsResponse([{ id: "a1", sync_status: "SYNCING" }]);
      return financeApiResponses()(path);
    });
    api.post.mockResolvedValue({ data: { triggered: ["a1"] } });

    renderHarness({ syncOnMount: true, onState: (s) => states.push(s) });
    await act(async () => {});
    expect(states.at(-1).syncing).toBe(true);

    // avança tempo suficiente pra estourar o teto de tentativas (24 × 5s)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(24 * 5000);
    });

    expect(states.at(-1).syncing).toBe(false);

    const callsAtGiveUp = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;

    // depois de desistir, mais tempo passando não deve gerar mais checagens
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30000);
    });
    const callsAfter = api.get.mock.calls.filter((c) => c[0] === "/bank-accounts").length;
    expect(callsAfter).toBe(callsAtGiveUp);

    vi.useRealTimers();
  });

  it("triggerSync(true) dispara sync-all com force=true", async () => {
    api.get.mockImplementation(financeApiResponses());
    api.post.mockResolvedValue({ data: { triggered: [] } });

    let latest;
    renderHarness({ syncOnMount: false, onState: (s) => (latest = s) });
    await act(async () => {});

    await act(async () => {
      await latest.triggerSync(true);
    });

    expect(api.post).toHaveBeenCalledWith(
      "/bank-accounts/sync-all",
      null,
      { params: { force: true } }
    );
  });
});
