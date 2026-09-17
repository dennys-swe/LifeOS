import { beforeEach, describe, expect, it } from "vitest";

import { clearFinanceCache, loadFinanceCache, saveFinanceCache } from "./financeCache";

beforeEach(() => {
  sessionStorage.clear();
});

describe("financeCache", () => {
  it("round-trips o que foi salvo", () => {
    const cache = new Map([["9-2026", { payables: [{ id: "1" }] }]]);
    saveFinanceCache(cache);

    const loaded = loadFinanceCache();
    expect(loaded.get("9-2026")).toEqual({ payables: [{ id: "1" }] });
  });

  it("clearFinanceCache() remove o cache — sem isso, vazaria entre logins na mesma aba", () => {
    saveFinanceCache(new Map([["9-2026", { payables: [] }]]));

    clearFinanceCache();

    expect(loadFinanceCache().size).toBe(0);
  });

  it("sem cache salvo, devolve um Map vazio", () => {
    expect(loadFinanceCache().size).toBe(0);
  });
});
