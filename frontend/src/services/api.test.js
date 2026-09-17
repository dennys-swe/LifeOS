import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/financeCache", () => ({
  clearFinanceCache: vi.fn(),
}));

import { clearFinanceCache } from "../lib/financeCache";
import { clearToken, setToken } from "./api";

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

describe("clearToken", () => {
  it("também limpa o cache financeiro — sem isso vaza entre usuários na mesma aba", () => {
    setToken("um-token");

    clearToken();

    expect(localStorage.getItem("lifeos_token")).toBeNull();
    expect(clearFinanceCache).toHaveBeenCalledTimes(1);
  });
});
