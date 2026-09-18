import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/financeCache", () => ({
  clearFinanceCache: vi.fn(),
}));

import { clearFinanceCache } from "../lib/financeCache";
import {
  __resetRequestTrackingForTests,
  clearToken,
  setToken,
  shouldShowColdStartBanner,
  trackRequestEnd,
  trackRequestStart,
  trackRequestSuccess,
} from "./api";

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  __resetRequestTrackingForTests();
});

describe("clearToken", () => {
  it("também limpa o cache financeiro — sem isso vaza entre usuários na mesma aba", () => {
    setToken("um-token");

    clearToken();

    expect(localStorage.getItem("lifeos_token")).toBeNull();
    expect(clearFinanceCache).toHaveBeenCalledTimes(1);
  });
});

describe("shouldShowColdStartBanner (issue #23, P2 — banner de cold start)", () => {
  it("false quando não há requisição pendente", () => {
    expect(shouldShowColdStartBanner()).toBe(false);
  });

  it("false quando a requisição pendente ainda não passou do threshold", () => {
    const req = {};
    trackRequestStart(req, Date.now() - 1000);
    expect(shouldShowColdStartBanner()).toBe(false);
    trackRequestEnd(req);
  });

  it("true quando a requisição pendente passou do threshold e faz tempo que não há resposta bem-sucedida", () => {
    const req = {};
    trackRequestStart(req, Date.now() - 6000);
    expect(shouldShowColdStartBanner()).toBe(true);
    trackRequestEnd(req);
  });

  it("volta a false depois que a requisição lenta termina", () => {
    const req = {};
    trackRequestStart(req, Date.now() - 6000);
    expect(shouldShowColdStartBanner()).toBe(true);

    trackRequestEnd(req);

    expect(shouldShowColdStartBanner()).toBe(false);
  });

  it("false mesmo com requisição lenta, se o backend respondeu com sucesso recentemente", () => {
    // Achado no code-review: sem essa checagem, um sync manual de verdade
    // (Pluggy) ou uma query pesada passando de 5s com o backend já bem
    // acordado mostrava "aquecendo o servidor" de forma enganosa.
    trackRequestSuccess(Date.now() - 5000); // respondeu com sucesso há 5s

    const req = {};
    trackRequestStart(req, Date.now() - 6000);
    expect(shouldShowColdStartBanner()).toBe(false);
    trackRequestEnd(req);
  });

  it("nunca ter tido uma resposta bem-sucedida conta como 'inativo há tempo o bastante' (1ª carga do app)", () => {
    const req = {};
    trackRequestStart(req, Date.now() - 6000);
    // não chama trackRequestSuccess — simula a 1ª requisição da sessão
    expect(shouldShowColdStartBanner()).toBe(true);
    trackRequestEnd(req);
  });
});
