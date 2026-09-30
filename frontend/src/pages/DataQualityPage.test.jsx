import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FinanceProvider } from "../context/FinanceContext";
import api from "../services/api";
import DataQualityPage from "./DataQualityPage";

vi.mock("../services/api", () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

const tx = (over = {}) => ({
  id: "t1",
  date: "2026-09-14",
  description: "PAGAMENTO ON LINE",
  amount: "769.01",
  type: "INCOME",
  is_transfer: false,
  category_name: null,
  ...over,
});

const issue = (over = {}) => ({
  id: "i1",
  kind: "system_says_transfer",
  severity: "high",
  status: "open",
  detected_at: "2026-10-01T10:00:00",
  detail: {},
  transactions: [tx()],
  fix_available: true,
  needs_category: false,
  ...over,
});

const uncategorized = issue({
  id: "i2",
  kind: "uncategorized_expense",
  severity: "info",
  transactions: [tx({ id: "t2", description: "PASTAS LTDA", amount: "35.00", type: "EXPENSE" })],
  needs_category: true,
});

const largeIncome = issue({
  id: "i3",
  kind: "large_unusual_income",
  severity: "info",
  transactions: [tx({ id: "t3", description: "Transferência Recebida|Fulano", amount: "3376.82" })],
  fix_available: false,
});

const transferPreview = {
  issue_id: "i1",
  kind: "system_says_transfer",
  fix_available: true,
  needs_category: false,
  changes: [
    {
      transaction_id: "t1",
      description: "PAGAMENTO ON LINE",
      amount: "769.01",
      date: "2026-09-14",
      type: "INCOME",
      field: "is_transfer",
      old: "false",
      new: "true",
    },
  ],
  income_removed: "769.01",
  expense_removed: "0.00",
  already_fixed: false,
};

const summaryData = { open_total: 1, by_severity: { high: 1, warn: 0, info: 0 }, by_kind: {}, last_detected_at: "2026-10-01T10:00:00" };

let issuesResponse;

function mockApi() {
  api.get.mockImplementation((path) => {
    if (path === "/payables") return Promise.resolve({ data: [] });
    if (path === "/categories")
      return Promise.resolve({
        data: [
          { id: "c1", name: "Alimentação", kind: "EXPENSE" },
          { id: "c2", name: "Salário", kind: "INCOME" },
        ],
      });
    if (path === "/summary") return Promise.resolve({ data: null });
    if (path === "/data-quality/issues") return Promise.resolve({ data: issuesResponse });
    if (path === "/data-quality/summary") return Promise.resolve({ data: summaryData });
    if (path.endsWith("/preview")) return Promise.resolve({ data: transferPreview });
    return Promise.reject(new Error(`unexpected GET ${path}`));
  });
  api.post.mockResolvedValue({ data: {} });
}

async function renderPage() {
  const utils = render(
    <MemoryRouter>
      <FinanceProvider month={10} year={2026}>
        <DataQualityPage />
      </FinanceProvider>
    </MemoryRouter>
  );
  await act(async () => {});
  return utils;
}

const click = async (el) => {
  await act(async () => {
    fireEvent.click(el);
  });
};

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  issuesResponse = [issue(), uncategorized, largeIncome];
  mockApi();
});

describe("DataQualityPage — Saúde dos dados (issue #200)", () => {
  it("agrupa os avisos por gravidade, do mais grave ao menos", async () => {
    await renderPage();

    const high = screen.getByTestId("group-high");
    const info = screen.getByTestId("group-info");
    expect(within(high).getByText("Parece dinheiro que só mudou de lugar")).toBeTruthy();
    expect(within(info).getAllByTestId("issue-card")).toHaveLength(2);
    expect(high.compareDocumentPosition(info) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByTestId("group-warn")).toBeNull();
  });

  it("mostra a data e o valor das transações de cada aviso", async () => {
    await renderPage();

    const card = within(screen.getByTestId("group-high")).getByTestId("issue-card");
    expect(card.textContent).toContain("14/09/2026");
    expect(card.textContent).toContain("PAGAMENTO ON LINE");
    expect(card.textContent).toContain("769,01");
  });

  it("mostra estado vazio quando não há avisos", async () => {
    issuesResponse = [];
    await renderPage();

    expect(screen.getByText("Tudo certo por aqui")).toBeTruthy();
    expect(screen.queryByTestId("issue-card")).toBeNull();
  });

  it("mostra a prévia do que muda antes de qualquer gravação", async () => {
    await renderPage();
    const card = within(screen.getByTestId("group-high")).getByTestId("issue-card");

    await click(within(card).getByText("Ver o que muda"));

    const preview = within(card).getByTestId("issue-preview");
    expect(preview.textContent).toContain("Marcar como transferência: PAGAMENTO ON LINE");
    expect(preview.textContent).toContain("Sai da renda");
    expect(preview.textContent).toContain("769,01");
    expect(api.post).not.toHaveBeenCalled();
  });

  it("aplica a correção só depois da prévia e tira o aviso da lista", async () => {
    await renderPage();
    const card = within(screen.getByTestId("group-high")).getByTestId("issue-card");
    await click(within(card).getByText("Ver o que muda"));

    await click(within(card).getByText("Aplicar correção"));

    expect(api.post).toHaveBeenCalledWith("/data-quality/issues/i1/apply", { category_id: null });
    expect(screen.queryByTestId("group-high")).toBeNull();
    expect(screen.getByText("Correção aplicada.")).toBeTruthy();
  });

  it("cancelar a prévia volta ao botão sem gravar nada", async () => {
    await renderPage();
    const card = within(screen.getByTestId("group-high")).getByTestId("issue-card");
    await click(within(card).getByText("Ver o que muda"));

    await click(within(card).getByText("Cancelar"));

    expect(within(card).queryByTestId("issue-preview")).toBeNull();
    expect(within(card).getByText("Ver o que muda")).toBeTruthy();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("despesa sem categoria exige escolher a categoria, só de despesa, antes da prévia", async () => {
    await renderPage();
    const card = within(screen.getByTestId("group-info")).getAllByTestId("issue-card")[0];
    const button = within(card).getByText("Ver o que muda");
    expect(button.disabled).toBe(true);

    const select = within(card).getByLabelText("Escolher categoria");
    expect(within(select).queryByText("Salário")).toBeNull();
    fireEvent.change(select, { target: { value: "c1" } });

    expect(within(card).getByText("Ver o que muda").disabled).toBe(false);
    await click(within(card).getByText("Ver o que muda"));
    expect(api.get).toHaveBeenCalledWith("/data-quality/issues/i2/preview", {
      params: { category_id: "c1" },
    });
  });

  it("envia a categoria escolhida ao aplicar", async () => {
    issuesResponse = [uncategorized];
    await renderPage();
    const card = screen.getByTestId("issue-card");
    fireEvent.change(within(card).getByLabelText("Escolher categoria"), { target: { value: "c1" } });
    await click(within(card).getByText("Ver o que muda"));

    await click(within(card).getByText("Aplicar correção"));

    expect(api.post).toHaveBeenCalledWith("/data-quality/issues/i2/apply", { category_id: "c1" });
  });

  it("entrada grande não tem correção automática, só 'Está certo'", async () => {
    issuesResponse = [largeIncome];
    await renderPage();
    const card = screen.getByTestId("issue-card");

    expect(within(card).queryByText("Ver o que muda")).toBeNull();
    await click(within(card).getByText("Está certo"));

    expect(api.post).toHaveBeenCalledWith("/data-quality/issues/i3/dismiss");
    expect(screen.queryByTestId("issue-card")).toBeNull();
    expect(screen.getByText("Marcado como correto.")).toBeTruthy();
  });

  it("avisa quando a prévia mostra que já foi corrigido", async () => {
    api.get.mockImplementation((path) => {
      if (path.endsWith("/preview"))
        return Promise.resolve({ data: { ...transferPreview, changes: [], already_fixed: true } });
      if (path === "/data-quality/issues") return Promise.resolve({ data: [issue()] });
      if (path === "/data-quality/summary") return Promise.resolve({ data: summaryData });
      if (path === "/categories") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: path === "/payables" ? [] : null });
    });
    await renderPage();
    const card = screen.getByTestId("issue-card");

    await click(within(card).getByText("Ver o que muda"));

    expect(within(card).getByTestId("issue-preview").textContent).toContain("já foi corrigido");
  });

  it("mostra o erro da API e mantém o aviso quando a correção falha", async () => {
    await renderPage();
    const card = within(screen.getByTestId("group-high")).getByTestId("issue-card");
    await click(within(card).getByText("Ver o que muda"));
    api.post.mockRejectedValueOnce({ response: { data: { detail: "Este achado já foi tratado" } } });

    await click(within(card).getByText("Aplicar correção"));

    expect(within(card).getByText("Este achado já foi tratado")).toBeTruthy();
    expect(screen.getByTestId("group-high")).toBeTruthy();
  });

  it("'Verificar agora' roda a auditoria e recarrega a lista", async () => {
    issuesResponse = [];
    await renderPage();
    issuesResponse = [issue()];

    await click(screen.getByText("Verificar agora"));

    expect(api.post).toHaveBeenCalledWith("/data-quality/run");
    expect(screen.getByTestId("group-high")).toBeTruthy();
  });

  it("mostra mensagem quando não consegue carregar", async () => {
    api.get.mockImplementation((path) => {
      if (path === "/data-quality/issues") return Promise.reject(new Error("fora"));
      if (path === "/categories") return Promise.resolve({ data: [] });
      return Promise.resolve({ data: path === "/payables" ? [] : null });
    });
    await renderPage();

    expect(screen.getByText("Não foi possível carregar os avisos agora.")).toBeTruthy();
  });

  it("mostra a data da última verificação", async () => {
    await renderPage();

    expect(screen.getByText(/Última verificação:/)).toBeTruthy();
  });
});
