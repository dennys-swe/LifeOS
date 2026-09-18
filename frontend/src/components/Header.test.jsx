import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../services/api";
import { AuthProvider } from "../context/AuthContext";
import { FinanceProvider } from "../context/FinanceContext";
import { ThemeProvider } from "../context/ThemeContext";
import Header from "./Header";

vi.mock("../services/api", () => ({
  default: { get: vi.fn(), post: vi.fn() },
  getToken: () => null,
  clearToken: vi.fn(),
  setToken: vi.fn(),
}));

function defaultResponse(path) {
  if (path === "/bank-accounts") return Promise.resolve({ data: [] });
  if (path === "/payables") return Promise.resolve({ data: [] });
  if (path === "/categories") return Promise.resolve({ data: [] });
  if (path === "/summary") return Promise.resolve({ data: {} });
  return Promise.reject(new Error(`unexpected GET ${path}`));
}

function mockApiResponses() {
  api.get.mockImplementation(defaultResponse);
}

function renderHeader() {
  return render(
    <AuthProvider>
      <ThemeProvider>
        <FinanceProvider month={1} year={2026}>
          <Header />
        </FinanceProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  mockApiResponses();
});

describe("Header — botão Sincronizar tudo (issue #118)", () => {
  it("chama sync-all com force=true ao clicar", async () => {
    api.post.mockResolvedValue({ data: { triggered: [] } });

    const { getByTitle } = renderHeader();
    await act(async () => {});

    await act(async () => {
      getByTitle("Sincronizar todas as contas agora").click();
    });

    expect(api.post).toHaveBeenCalledWith(
      "/bank-accounts/sync-all",
      null,
      { params: { force: true } }
    );
  });

  it("fica desabilitado enquanto uma sincronização está em andamento", async () => {
    // `syncing` vira true assim que o POST responde com contas disparadas —
    // não precisa nem chegar a pollar pra já refletir no botão.
    api.post.mockResolvedValue({ data: { triggered: ["a1"] } });

    const { getByTitle } = renderHeader();
    await act(async () => {});

    await act(async () => {
      getByTitle("Sincronizar todas as contas agora").click();
    });

    const button = getByTitle("Sincronizar todas as contas agora");
    expect(button.disabled).toBe(true);
  });
});
