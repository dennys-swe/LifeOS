import { act, render, screen } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import api from "../services/api";
import { FinanceProvider, useFinance } from "./FinanceContext";

vi.mock("../services/api", () => ({
  default: { get: vi.fn() },
}));

// 8 chamadas por fetch: as 3 originais (payables/categories/summary) + as 5
// próprias do DashboardPage que passaram a viver aqui (issue #141).
function mockApiResponses() {
  api.get.mockImplementation((path) => {
    if (path === "/payables") return Promise.resolve({ data: [] });
    if (path === "/categories") return Promise.resolve({ data: [] });
    if (path === "/summary") return Promise.resolve({ data: {} });
    if (path === "/payables/upcoming") return Promise.resolve({ data: [] });
    if (path === "/credit-card-bills") return Promise.resolve({ data: [] });
    if (path === "/insights") return Promise.resolve({ data: { insights: [] } });
    if (path === "/summary/history") return Promise.resolve({ data: { months: [] } });
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

// `needsDashboardData=true` por padrão nos testes abaixo — simula o usuário
// na rota do dashboard, que é o caso que a maioria deles quer exercitar. Os
// testes que exercitam especificamente `needsDashboardData=false` (issue
// #141 — não pagar os 5 extras fora do dashboard) passam a prop explícita.
function Harness({ onRefreshSeen, needsDashboardData = true }) {
  const [month, setMonth] = useState(1);
  const [year] = useState(2026);
  return (
    <FinanceProvider month={month} year={year} needsDashboardData={needsDashboardData}>
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
  it("não refaz as 8 chamadas ao voltar para um mês já buscado nesta sessão", async () => {
    const seen = [];
    render(<Harness onRefreshSeen={(fn) => seen.push(fn)} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(8); // janeiro

    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    expect(api.get).toHaveBeenCalledTimes(16); // fevereiro, ainda não visto

    await act(async () => {
      screen.getByText("voltar para janeiro").click();
    });
    // janeiro já foi buscado nesta sessão — não deve refazer as 8 chamadas
    expect(api.get).toHaveBeenCalledTimes(16);
  });

  it("refresh() explícito invalida o cache e refaz as 8 chamadas", async () => {
    render(<Harness onRefreshSeen={() => {}} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(8);

    await act(async () => {
      screen.getByText("refresh").click();
    });
    expect(api.get).toHaveBeenCalledTimes(16);
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
    expect(api.get).toHaveBeenCalledTimes(8);
  });

  it("entrada de cache sem fetchedAt (formato de antes desta mudança) é tratada como velha", async () => {
    sessionStorage.setItem(
      "lifeos-finance-cache-v1",
      JSON.stringify({ "1-2026": { payables: [], categories: [], summary: {} } })
    );

    render(<Harness onRefreshSeen={() => {}} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(8);
  });

  it("entrada de cache com fetchedAt recente mas sem os campos do dashboard (issue #141) é revalidada mesmo dentro do TTL", async () => {
    sessionStorage.setItem(
      "lifeos-finance-cache-v1",
      JSON.stringify({
        "1-2026": { payables: [], categories: [], summary: {}, fetchedAt: Date.now() },
      })
    );

    render(<Harness onRefreshSeen={() => {}} />);

    await act(async () => {});
    // fetchedAt está dentro do TTL, mas `upcoming` nunca existiu nessa
    // entrada — precisa revalidar mesmo assim, senão o dashboard fica com
    // faturas/insights/histórico vazios até o cache envelhecer 3min.
    expect(api.get).toHaveBeenCalledTimes(8);
  });

  it("revalida em segundo plano ao voltar o foco da aba com cache velho", async () => {
    render(<Harness onRefreshSeen={() => {}} />);
    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(8);

    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(api.get).toHaveBeenCalledTimes(16);
    vi.useRealTimers();
  });

  it("não revalida em foco quando o cache ainda está fresco", async () => {
    render(<Harness onRefreshSeen={() => {}} />);
    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(8);

    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(api.get).toHaveBeenCalledTimes(8);
  });

  it("visibilitychange e focus disparando juntos revalidam só uma vez", async () => {
    render(<Harness onRefreshSeen={() => {}} />);
    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(8);

    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);

    // navegadores tipicamente disparam os dois eventos ao voltar pra aba
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
      window.dispatchEvent(new Event("focus"));
    });

    // 8 da carga inicial + 8 de UMA revalidação (não 8+16=24, que seria duas)
    expect(api.get).toHaveBeenCalledTimes(16);
    vi.useRealTimers();
  });

  it("fora do dashboard (needsDashboardData=false) busca só as 3 chamadas core, sem os 5 extras", async () => {
    render(<Harness onRefreshSeen={() => {}} needsDashboardData={false} />);

    await act(async () => {});
    expect(api.get).toHaveBeenCalledTimes(3);

    // refresh() de outra página (ex: editar uma regra em Configurações) não
    // deve pagar os 5 extras do dashboard, que ninguém está olhando agora.
    await act(async () => {
      screen.getByText("refresh").click();
    });
    expect(api.get).toHaveBeenCalledTimes(6);
  });

  it("ao navegar pro dashboard, busca os 5 extras que ficaram pendentes de quando a rota não era o dashboard", async () => {
    function NavigatingHarness() {
      const [onDashboard, setOnDashboard] = useState(false);
      return (
        <FinanceProvider month={1} year={2026} needsDashboardData={onDashboard}>
          <RefreshButton />
          <button onClick={() => setOnDashboard(true)}>ir para o dashboard</button>
        </FinanceProvider>
      );
    }

    render(<NavigatingHarness />);
    await act(async () => {});
    // 3 chamadas core, fora do dashboard — extras puladas de propósito
    expect(api.get).toHaveBeenCalledTimes(3);

    await act(async () => {
      screen.getByText("ir para o dashboard").click();
    });
    // fetchFinance não tem um caminho de "só os extras" — ao perceber que
    // faltam, refaz o fetch inteiro (3 core + 5 extras). Simplicidade
    // proposital: esse caso só acontece na primeira vez que o dashboard é
    // aberto após uma mutação em outra tela, não a cada troca de aba.
    expect(api.get).toHaveBeenCalledTimes(11);
  });

  it("updateBills sincroniza o cache — sobrevive a trocar de mês e voltar, sem precisar de refresh()", async () => {
    // Simula o servidor já refletindo a edição — igual à vida real, onde o
    // PATCH roda ANTES de updateBills ser chamado (handleSaveAlias/
    // handlePickColor em DashboardPage.jsx). updateBills dispara um
    // refetch silencioso em seguida (achado de review — sincroniza
    // `payables`, cujo título também pode ter mudado); sem esse mock
    // devolver o mesmo dado editado, esse refetch reverteria a edição
    // otimista pra o snapshot genérico do mock padrão.
    api.get.mockImplementation((path) => {
      if (path === "/credit-card-bills") {
        return Promise.resolve({ data: [{ id: "b1", custom_color_hex: "#7c3aed" }] });
      }
      if (path === "/payables") return Promise.resolve({ data: [] });
      if (path === "/categories") return Promise.resolve({ data: [] });
      if (path === "/summary") return Promise.resolve({ data: {} });
      if (path === "/payables/upcoming") return Promise.resolve({ data: [] });
      if (path === "/insights") return Promise.resolve({ data: { insights: [] } });
      if (path === "/summary/history") return Promise.resolve({ data: { months: [] } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    const seenBills = [];
    function BillsConsumer() {
      const { bills, updateBills } = useFinance();
      seenBills.push(bills);
      return (
        <button onClick={() => updateBills(() => [{ id: "b1", custom_color_hex: "#7c3aed" }])}>
          escolher cor
        </button>
      );
    }
    function BillsHarness() {
      const [month, setMonth] = useState(1);
      const [year] = useState(2026);
      return (
        <FinanceProvider month={month} year={year} needsDashboardData>
          <BillsConsumer />
          <button onClick={() => setMonth(2)}>ir para fevereiro</button>
          <button onClick={() => setMonth(1)}>voltar para janeiro</button>
        </FinanceProvider>
      );
    }

    render(<BillsHarness />);
    await act(async () => {});

    await act(async () => {
      screen.getByText("escolher cor").click();
    });

    // Antes da correção (issue #141, achado de review), `setBills` cru só
    // mudava o state — voltar pra janeiro lia `cacheRef` de novo e
    // sobrescrevia com a lista antiga, perdendo a cor escolhida.
    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    await act(async () => {
      screen.getByText("voltar para janeiro").click();
    });

    const lastSeen = seenBills[seenBills.length - 1];
    expect(lastSeen.find((b) => b.id === "b1")?.custom_color_hex).toBe("#7c3aed");
  });

  it("updateBills invalida os extras de outros meses já em cache — nome/cor de cartão é propagado pelo backend a todo mês (achado de review)", async () => {
    function BillsConsumer() {
      const { updateBills } = useFinance();
      return (
        <button
          onClick={() =>
            updateBills((prev) => prev.map((b) => ({ ...b, custom_card_name: "Novo Nome" })))
          }
        >
          renomear
        </button>
      );
    }
    function MultiMonthHarness() {
      const [month, setMonth] = useState(1);
      const [year] = useState(2026);
      return (
        <FinanceProvider month={month} year={year} needsDashboardData>
          <BillsConsumer />
          <button onClick={() => setMonth(2)}>ir para fevereiro</button>
          <button onClick={() => setMonth(1)}>voltar para janeiro</button>
        </FinanceProvider>
      );
    }

    render(<MultiMonthHarness />);
    await act(async () => {}); // janeiro: 8 chamadas
    expect(api.get).toHaveBeenCalledTimes(8);

    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    // fevereiro ainda não visto nesta sessão: mais 8 chamadas
    expect(api.get).toHaveBeenCalledTimes(16);

    await act(async () => {
      screen.getByText("voltar para janeiro").click();
    });
    // janeiro já em cache — nenhuma chamada nova
    expect(api.get).toHaveBeenCalledTimes(16);

    await act(async () => {
      screen.getByText("renomear").click();
    });
    // updateBills dispara um refetch silencioso do mês ATIVO (janeiro) —
    // sincroniza `payables`, cujo título também pode ter sido reescrito
    // pelo backend (achado de review): +8 chamadas.
    expect(api.get).toHaveBeenCalledTimes(24);

    await act(async () => {
      screen.getByText("ir para fevereiro").click();
    });
    // fevereiro tinha os extras invalidados pela renomeação feita em
    // janeiro (o cartão é o mesmo, o backend propaga o nome/cor pra toda
    // fatura dele) — precisa buscar de novo, mesmo ainda dentro do TTL.
    expect(api.get).toHaveBeenCalledTimes(32);
  });

  it("updateBills durante um fetch em voo não é sobrescrito quando esse fetch resolve depois (achado de review)", async () => {
    let resolveBills;
    const billsPending = new Promise((resolve) => {
      resolveBills = resolve;
    });

    // Cache já velho (fora do TTL) — dispara uma revalidação silenciosa no
    // mount, que fica presa em /credit-card-bills até resolveBills().
    sessionStorage.setItem(
      "lifeos-finance-cache-v1",
      JSON.stringify({
        "1-2026": {
          payables: [],
          categories: [],
          summary: {},
          upcoming: [],
          bills: [{ id: "b1", custom_color_hex: null }],
          prevSummary: null,
          insights: [],
          history: [],
          fetchedAt: Date.now() - 10 * 60 * 1000,
        },
      })
    );

    // A 1ª chamada a /credit-card-bills (revalidação automática do mount,
    // por TTL) fica presa em `billsPending` e devolve o valor PRÉ-edição
    // quando liberada. Qualquer chamada seguinte (inclusive a rodada
    // pendente que o fix do achado de review dispara assim que a 1ª
    // termina) devolve o valor JÁ EDITADO — como na vida real, onde o PATCH
    // sempre roda ANTES de updateBills ser chamado, então o servidor já
    // reflete a edição em qualquer GET subsequente.
    let creditCardBillsCalls = 0;
    api.get.mockImplementation((path) => {
      if (path === "/credit-card-bills") {
        creditCardBillsCalls += 1;
        if (creditCardBillsCalls === 1) {
          return billsPending.then(() => ({ data: [{ id: "b1", custom_color_hex: null }] }));
        }
        return Promise.resolve({ data: [{ id: "b1", custom_color_hex: "#7c3aed" }] });
      }
      if (path === "/payables") return Promise.resolve({ data: [] });
      if (path === "/categories") return Promise.resolve({ data: [] });
      if (path === "/summary") return Promise.resolve({ data: {} });
      if (path === "/payables/upcoming") return Promise.resolve({ data: [] });
      if (path === "/insights") return Promise.resolve({ data: { insights: [] } });
      if (path === "/summary/history") return Promise.resolve({ data: { months: [] } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    const seenBills = [];
    function BillsConsumer() {
      const { bills, updateBills } = useFinance();
      seenBills.push(bills);
      return (
        <button onClick={() => updateBills(() => [{ id: "b1", custom_color_hex: "#7c3aed" }])}>
          colorir
        </button>
      );
    }

    render(
      <FinanceProvider month={1} year={2026} needsDashboardData>
        <BillsConsumer />
      </FinanceProvider>
    );

    // Cache velho aplicado na hora; a revalidação silenciosa dispara mas
    // fica presa em /credit-card-bills (billsPending ainda não resolvido).
    await act(async () => {});

    // Usuário escolhe uma cor ENQUANTO a revalidação ainda está em voo.
    await act(async () => {
      screen.getByText("colorir").click();
    });

    // Agora a revalidação (que buscou o snapshot PRÉ-edição) resolve.
    await act(async () => {
      resolveBills();
      await billsPending;
    });

    // A cor escolhida não pode ter sido revertida pelo snapshot antigo.
    const lastSeen = seenBills[seenBills.length - 1];
    expect(lastSeen.find((b) => b.id === "b1").custom_color_hex).toBe("#7c3aed");
  });

  it("updateBills durante um fetch em voo agenda uma rodada nova assim que ele termina, em vez de perder a sincronização (achado de review)", async () => {
    let resolvePending;
    const pending = new Promise((resolve) => {
      resolvePending = resolve;
    });

    // /credit-card-bills fica preso (mesmo mount-TTL-triggered da revalidação)
    // enquanto tudo mais resolve na hora — só pra medir quantas vezes
    // /payables é chamado a cada rodada de fetchFinance.
    let payablesCalls = 0;
    api.get.mockImplementation((path) => {
      if (path === "/credit-card-bills") return pending.then(() => ({ data: [] }));
      if (path === "/payables") {
        payablesCalls += 1;
        return Promise.resolve({ data: [] });
      }
      if (path === "/categories") return Promise.resolve({ data: [] });
      if (path === "/summary") return Promise.resolve({ data: {} });
      if (path === "/payables/upcoming") return Promise.resolve({ data: [] });
      if (path === "/insights") return Promise.resolve({ data: { insights: [] } });
      if (path === "/summary/history") return Promise.resolve({ data: { months: [] } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    sessionStorage.setItem(
      "lifeos-finance-cache-v1",
      JSON.stringify({
        "1-2026": {
          payables: [],
          categories: [],
          summary: {},
          upcoming: [],
          bills: [],
          prevSummary: null,
          insights: [],
          history: [],
          fetchedAt: Date.now() - 10 * 60 * 1000,
        },
      })
    );

    function RenameConsumer() {
      const { updateBills } = useFinance();
      return <button onClick={() => updateBills((prev) => prev)}>renomear</button>;
    }

    render(
      <FinanceProvider month={1} year={2026} needsDashboardData>
        <RenameConsumer />
      </FinanceProvider>
    );

    // Mount: cache velho aplicado na hora, revalidação silenciosa dispara e
    // fica presa em /credit-card-bills. /payables já rodou uma vez aqui.
    await act(async () => {});
    expect(payablesCalls).toBe(1);

    // updateBills tenta sincronizar ENQUANTO a revalidação ainda está em
    // voo — o guard de dedup descarta a chamada nova, mas marca "pendente".
    await act(async () => {
      screen.getByText("renomear").click();
    });
    expect(payablesCalls).toBe(1); // nenhuma chamada nova ainda

    // A revalidação presa finalmente resolve — deve disparar a rodada
    // pendente sozinha, sem precisar de outra ação do usuário.
    await act(async () => {
      resolvePending();
      await pending;
    });
    expect(payablesCalls).toBe(2);
  });

  it("revalidação silenciosa fora do dashboard não apaga extras já cacheados de uma visita anterior (achado de review)", async () => {
    api.get.mockImplementation((path) => {
      if (path === "/payables") return Promise.resolve({ data: [] });
      if (path === "/categories") return Promise.resolve({ data: [] });
      if (path === "/summary") return Promise.resolve({ data: {} });
      if (path === "/payables/upcoming") return Promise.resolve({ data: [{ id: "u1" }] });
      if (path === "/credit-card-bills") return Promise.resolve({ data: [{ id: "b1" }] });
      if (path === "/insights") return Promise.resolve({ data: { insights: [{ id: "i1" }] } });
      if (path === "/summary/history") return Promise.resolve({ data: { months: [{ month: 1 }] } });
      return Promise.reject(new Error(`unexpected ${path}`));
    });

    function ToggleHarness() {
      const [onDashboard, setOnDashboard] = useState(true);
      return (
        <FinanceProvider month={1} year={2026} needsDashboardData={onDashboard}>
          <Consumer2 />
          <button onClick={() => setOnDashboard(false)}>sair do dashboard</button>
          <button onClick={() => setOnDashboard(true)}>voltar pro dashboard</button>
        </FinanceProvider>
      );
    }
    const seenUpcoming = [];
    function Consumer2() {
      const { upcoming } = useFinance();
      seenUpcoming.push(upcoming);
      return null;
    }

    render(<ToggleHarness />);
    await act(async () => {}); // carga inicial no dashboard: upcoming = [{id:"u1"}]
    expect(seenUpcoming[seenUpcoming.length - 1]).toEqual([{ id: "u1" }]);

    await act(async () => {
      screen.getByText("sair do dashboard").click();
    });

    // Fora do dashboard, cache envelhece além do TTL e o foco da aba
    // dispara uma revalidação silenciosa — só dos 3 core, já que
    // needsDashboardData é false agora.
    vi.useFakeTimers();
    vi.setSystemTime(Date.now() + 10 * 60 * 1000);
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    vi.useRealTimers();

    // Marca daqui pra frente — o efeito de "faltam os extras" já cura
    // sozinho até o fim do act() (os mocks resolvem na hora), então checar
    // só o valor FINAL não pegaria um flicker transitório. Tem que checar
    // TODO render entre o clique e o fim, não só o último.
    const idxBeforeReturn = seenUpcoming.length;

    await act(async () => {
      screen.getByText("voltar pro dashboard").click();
    });

    // Antes da correção (achado de review), essa revalidação fora do
    // dashboard sobrescrevia a entrada inteira do cache, apagando
    // `upcoming` — o dashboard reabria com a lista vazia (mesmo que um
    // refetch corretivo (`missingExtras`) resolvesse isso logo em seguida)
    // — o mesmo flicker que essa funcionalidade existe pra evitar.
    const rendersAfterReturn = seenUpcoming.slice(idxBeforeReturn);
    expect(rendersAfterReturn.every((u) => u.length > 0)).toBe(true);
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
      if (path === "/payables/upcoming") return Promise.resolve({ data: [] });
      if (path === "/credit-card-bills") return Promise.resolve({ data: [] });
      if (path === "/insights") return Promise.resolve({ data: { insights: [] } });
      if (path === "/summary/history") return Promise.resolve({ data: { months: [] } });
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
