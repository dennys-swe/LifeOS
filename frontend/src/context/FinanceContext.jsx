import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useMountedRef } from "../hooks/useMountedRef";
import { useRevalidateOnFocus } from "../hooks/useRevalidateOnFocus";
import { loadFinanceCache, saveFinanceCache } from "../lib/financeCache";
import { STALE_TTL_MS } from "../lib/staleness";
import api from "../services/api";

const FinanceContext = createContext(null);

function prevMonthYear(month, year) {
  return month === 1 ? [12, year - 1] : [month - 1, year];
}

// Cache por "mês-ano" nesta sessão do navegador (issue #66). Sem isso, trocar
// de aba (Dashboard -> Extrato -> Dashboard) não desmontava o FinanceProvider
// (já está acima do Outlet em ProtectedLayout), mas voltar pra um mês/ano já
// buscado ainda refazia as 3 chamadas — causa real: `refresh` não era
// memoizado, então toda vez que o provider re-renderizava (ex: ao terminar
// um fetch) ele virava uma função nova, e efeitos em outras páginas que têm
// `refresh` como dependência (DashboardPage, PayablesPage) disparavam de
// novo — o de PayablesPage inclusive CHAMA refresh() dentro do próprio
// efeito, criando um loop de refetch a cada vez que a aba era aberta.
// sessionStorage sobrevive a um F5 (só nesta aba), então o reload também
// aproveita o último dado bom em vez de mostrar tela zerada. Limpo no
// logout em services/api.js (clearToken) — ver lib/financeCache.js.

// Cache sem expiração nunca pega mudança feita por fora desta aba (sync
// automático do cron, webhook da Pluggy, conciliação feita em outra aba) —
// só `refresh()` explícito depois de uma mutação local invalidava, então uma
// aba deixada aberta ficava com dado velho indefinidamente (só saía do ar no
// logout). `STALE_TTL_MS` (lib/staleness.js, compartilhado com
// BankAccountsPage) marca a partir de quando um dado cacheado é velho o
// bastante pra merecer revalidação silenciosa (mostra o cache na hora, sem
// tela de loading, e busca por baixo dos panos) — ao focar a aba de novo ou
// trocar de mês/ano. Uma entrada de cache de antes desta mudança não tem
// `fetchedAt` (`?? 0` cai no epoch), então já nasce "velha" e se autocorrige
// no primeiro foco/troca de mês após o deploy, sem precisar de migração de
// formato.

export function FinanceProvider({ children, month, year, needsDashboardData = false }) {
  const cacheRef = useRef(null);
  if (cacheRef.current === null) {
    cacheRef.current = loadFinanceCache();
  }
  const lastRefreshKeyRef = useRef(0);
  const mountedRef = useMountedRef();
  // Lido dentro de fetchFinance (não como dependência) — só o valor mais
  // recente no momento da chamada importa, sem precisar recriar o callback
  // a cada mudança de rota. Ver ProtectedLayout.jsx pra por que isso é
  // decidido pela rota, e não por um efeito do próprio DashboardPage.
  const needsDashboardDataRef = useRef(needsDashboardData);
  needsDashboardDataRef.current = needsDashboardData;
  // Chave do mês/ano exibido agora — checado no retorno de um fetch antes de
  // aplicar setState, senão uma resposta lenta de um mês antigo (ex: a
  // revalidação silenciosa de foco de aba) pode chegar depois do usuário já
  // ter trocado de mês e sobrescrever a tela com dado do mês errado.
  const activeKeyRef = useRef(`${month}-${year}`);
  // Evita revalidação duplicada quando `visibilitychange` e `focus` disparam
  // juntos ao voltar pra aba (comum nos navegadores) — sem isso, os dois
  // chamavam fetchFinance pro mesmo mês em paralelo.
  const revalidatingKeysRef = useRef(new Set());
  // Quando um fetch silencioso pro mesmo mês já está em voo e outro chega
  // (ex: updateBills tentando sincronizar payables logo após uma edição), o
  // guard acima descarta o segundo — mas descartar de vez perderia a
  // sincronização (achado de review): o fetch em voo pode ter sido
  // disparado ANTES da edição e voltar com dado pré-edição. Isto marca "tem
  // mais uma rodada pendente pra este mês", processada assim que o fetch em
  // voo terminar (ver `finally` de fetchFinance).
  const pendingRefetchRef = useRef(new Set());

  const cacheKey = `${month}-${year}`;
  const cachedEntry = cacheRef.current.get(cacheKey);

  const [payables, setPayables] = useState(() => cachedEntry?.payables ?? []);
  const [categories, setCategories] = useState(() => cachedEntry?.categories ?? []);
  const [summary, setSummary] = useState(() => cachedEntry?.summary ?? null);
  // Dados próprios do DashboardPage (issue #141) — vivem aqui, não num
  // useEffect da própria página, porque a página desmonta ao trocar de aba
  // (cada rota é lazy dentro do <Outlet>) e este provider não. Sem isso, o
  // dashboard "recarregava" (inclusive o gráfico de tendência) toda vez que
  // o usuário voltava pra essa tela, mesmo minutos depois de já ter
  // carregado.
  const [upcoming, setUpcoming] = useState(() => cachedEntry?.upcoming ?? []);
  const [bills, setBills] = useState(() => cachedEntry?.bills ?? []);
  const [prevSummary, setPrevSummary] = useState(() => cachedEntry?.prevSummary ?? null);
  const [insights, setInsights] = useState(() => cachedEntry?.insights ?? []);
  const [history, setHistory] = useState(() => cachedEntry?.history ?? []);
  const [loading, setLoading] = useState(() => !cachedEntry);
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Incrementada a cada updateBills() — usada por fetchFinance pra saber se
  // uma edição otimista aconteceu DURANTE um fetch em voo (achado de
  // review): sem isso, uma revalidação silenciosa que começou antes da
  // edição (TTL ou "faltam os extras") resolve depois dela e sobrescreve
  // `bills` com o snapshot pré-edição, fazendo a cor/apelido escolhido
  // "voltar" na tela mesmo já persistido no servidor.
  const billsVersionRef = useRef(0);

  // Identidade estável (sem closure sobre month/year/state) — pode entrar em
  // dependência de efeito sem recriar o efeito a cada render, mesma
  // preocupação que already causou o loop de refetch da issue #66.
  const fetchFinance = useCallback(async (key, m, y, { silent = false } = {}) => {
    if (silent) {
      if (revalidatingKeysRef.current.has(key)) {
        pendingRefetchRef.current.add(key);
        return;
      }
      revalidatingKeysRef.current.add(key);
    } else {
      setLoading(true);
    }
    try {
      const wantsExtras = needsDashboardDataRef.current;
      // Versão de `bills` ANTES de disparar as chamadas — se `updateBills`
      // incrementar isso enquanto elas estão em voo, sabemos que uma edição
      // otimista aconteceu nesse meio tempo e não deve ser sobrescrita pelo
      // snapshot (pré-edição) que está prestes a chegar do servidor.
      const billsVersionAtStart = billsVersionRef.current;
      const [pm, py] = prevMonthYear(m, y);
      // Todas as chamadas num único Promise.all — nenhuma depende do
      // resultado de outra (m/y já são conhecidos), então não tem motivo
      // pra esperar os 3 core resolverem antes de disparar os 5 extras.
      // Os 5 extras (issue #141) só são buscados quando a rota atual É o
      // dashboard (`needsDashboardData`, prop vinda de ProtectedLayout) —
      // `refresh()` é chamado de toda mutação em qualquer página
      // (convenção do projeto), e não vale pagar 5 chamadas a mais toda
      // vez que o usuário edita algo em Configurações/Extrato/etc. Quando
      // pulado, a entrada de cache simplesmente não ganha esses campos — o
      // mesmo caminho que já trata uma entrada de antes desta mudança
      // (`cached.upcoming === undefined`, abaixo) cobre isso: ao voltar
      // pro dashboard, o efeito percebe os campos ausentes e busca. Cada
      // extra tem catch próprio — se um falhar (ex: /insights
      // momentaneamente fora), não pode derrubar payables/categories/summary.
      const [payablesRes, catsRes, summaryRes, ...extraResults] = await Promise.all([
        api.get("/payables", { params: { month: m, year: y } }),
        api.get("/categories"),
        api.get("/summary", { params: { month: m, year: y } }),
        ...(wantsExtras
          ? [
              api.get("/payables/upcoming", { params: { days: 7 } }).catch(() => ({ data: [] })),
              api
                .get("/credit-card-bills", { params: { month: m, year: y } })
                .catch(() => ({ data: [] })),
              api
                .get("/summary", { params: { month: pm, year: py } })
                .catch(() => ({ data: null })),
              api
                .get("/insights", { params: { month: m, year: y } })
                .catch(() => ({ data: { insights: [] } })),
              api
                .get("/summary/history", { params: { months: 6 } })
                .catch(() => ({ data: { months: [] } })),
            ]
          : []),
      ]);
      if (!mountedRef.current) return;
      const data = {
        payables: payablesRes.data ?? [],
        categories: catsRes.data ?? [],
        summary: summaryRes.data ?? null,
        fetchedAt: Date.now(),
      };
      if (wantsExtras) {
        const [upcomingRes, billsRes, prevSummaryRes, insightsRes, historyRes] = extraResults;
        data.upcoming = upcomingRes.data ?? [];
        // Se uma edição otimista (updateBills) aconteceu enquanto esta
        // chamada estava em voo, o que já está no cache é mais recente que
        // o que acabou de chegar — mantém o que já sabemos em vez de
        // regredir pro snapshot pré-edição.
        data.bills =
          billsVersionRef.current === billsVersionAtStart
            ? billsRes.data ?? []
            : (cacheRef.current.get(key)?.bills ?? billsRes.data ?? []);
        data.prevSummary = prevSummaryRes.data ?? null;
        data.insights = insightsRes.data?.insights ?? [];
        data.history = historyRes.data?.months ?? [];
      }
      // Fora do dashboard (`!wantsExtras`), `data` não tem os 5 extras —
      // sobrescrever a entrada inteira apagaria extras que já estavam
      // cacheados de uma visita anterior ao dashboard (achado de review):
      // uma revalidação de foco de aba enquanto o usuário está em
      // Configurações, por exemplo, faria o dashboard voltar a mostrar
      // faturas/insights/histórico vazios ao ser reaberto — exatamente o
      // flicker que este cache inteiro existe pra evitar. Faz merge em vez
      // de substituir, preservando o que já sabia.
      cacheRef.current.set(key, wantsExtras ? data : { ...cacheRef.current.get(key), ...data });
      // Só aplica ao estado exibido se o usuário ainda estiver neste
      // mês/ano — a entrada de cache é gravada de qualquer forma (fica
      // pronta pra quando ele voltar pra este mês).
      if (key === activeKeyRef.current) {
        setPayables(data.payables);
        setCategories(data.categories);
        setSummary(data.summary);
        if (wantsExtras) {
          setUpcoming(data.upcoming);
          setBills(data.bills);
          setPrevSummary(data.prevSummary);
          setInsights(data.insights);
          setHistory(data.history);
        }
      }
      // Persistência em sessionStorage é só uma otimização de reload — se
      // falhar (quota, modo privado), o cache em memória já foi atualizado
      // e a tela já tem o dado certo; não pode derrubar os setState acima.
      try {
        saveFinanceCache(cacheRef.current);
      } catch {
        // sem persistência entre reloads nesta sessão, mas os dados na
        // tela e o cache em memória continuam corretos
      }
    } catch {
      // keep previous data on error
    } finally {
      if (silent) {
        revalidatingKeysRef.current.delete(key);
        // Alguém tentou revalidar este mês enquanto esta chamada estava em
        // voo e foi descartado pelo guard acima — refaz agora, pra não
        // perder uma sincronização pedida explicitamente (ex: updateBills
        // depois de renomear um cartão). `mountedRef` primeiro: sem isso,
        // um pedido pendente de antes do componente desmontar (ex: logout)
        // dispararia requisições de rede pra um provider que não existe
        // mais (achado de review).
        if (mountedRef.current && pendingRefetchRef.current.delete(key)) {
          fetchFinance(key, m, y, { silent: true });
        }
      } else if (mountedRef.current && key === activeKeyRef.current) {
        // Mesmo cuidado do setState acima: uma resposta velha (mês que o
        // usuário já trocou) não pode desligar o loading do mês atual, que
        // pode ainda estar buscando.
        setLoading(false);
      }
    }
  }, [mountedRef]);

  // Atualização otimista de `bills` que também escreve no cache (issue
  // #141, achado de review) — `refresh()` seria pesado demais pra uma
  // edição de apelido/cor: limpa o cache inteiro e força um fetch não
  // silencioso (loading=true), derrubando o hero e o gasto por categoria
  // pra skeleton só porque um campo de uma fatura mudou.
  const updateBills = useCallback(
    (updater) => {
      billsVersionRef.current += 1;
      // Efeitos colaterais (mutar `cacheRef`, escrever sessionStorage) NÃO
      // podem morar dentro do updater passado a `setBills` (achado de
      // review) — em `<StrictMode>` (main.jsx) o React invoca o updater 2x
      // de propósito pra flagrar impureza; aqui rodaria a invalidação de
      // outros meses e o `saveFinanceCache` em dobro. `prev` vem do cache
      // (sempre sincronizado com o state pra a chave ativa, ver
      // fetchFinance) em vez do `bills` do state — permite calcular tudo
      // fora do updater, que só recebe o valor pronto.
      const key = activeKeyRef.current;
      const existing = cacheRef.current.get(key);
      const next = updater(existing?.bills ?? []);
      if (existing) {
        cacheRef.current.set(key, { ...existing, bills: next });
      }
      // `custom_card_name`/`custom_color_hex` são do CARTÃO, não da
      // fatura — o backend propaga a mudança pra toda fatura do mesmo
      // `pluggy_account_id`, em QUALQUER mês, e além disso reescreve
      // `Payable.title` de cada fatura ligada (ver
      // `update_bill_customization`/`_sync_payable` no backend). Sem
      // isto, outro mês já visitado nesta sessão (e por isso em cache)
      // ficaria mostrando o nome/cor/título antigo até o cache expirar
      // (3min) — trocar de mês simplesmente lia o snapshot velho de
      // volta. Replicar o `updater` em cada entrada seria arriscado (o
      // de renomear casa por `bill.id`, específico da fatura, não do
      // cartão — aplicar errado podia "renomear" a fatura errada de
      // outro mês). Mais seguro: invalidar os extras de todo OUTRO mês
      // em cache, reaproveitando o mesmo caminho que já busca de novo
      // uma entrada sem esses campos (`cached.upcoming === undefined`,
      // no efeito de mount).
      for (const [otherKey, entry] of cacheRef.current) {
        if (otherKey === key) continue;
        cacheRef.current.set(otherKey, {
          payables: entry.payables,
          categories: entry.categories,
          summary: entry.summary,
          fetchedAt: entry.fetchedAt,
        });
      }
      try {
        saveFinanceCache(cacheRef.current);
      } catch {
        // mesma tolerância a falha de sessionStorage do resto do arquivo
      }
      setBills(next);
      // `payables` do mês ATIVO também pode ter título desatualizado (o
      // mesmo `_sync_payable` do backend reescreve o título do payable
      // ligado à fatura renomeada) — diferente de `bills`, não dá pra
      // corrigir isso otimisticamente no cliente sem o backend expor qual
      // payable pertence a qual cartão. Busca silenciosa (sem
      // `loading=true`, sem flash) resolve isso em segundo plano.
      fetchFinance(activeKeyRef.current, month, year, { silent: true });
    },
    [month, year, fetchFinance]
  );

  useEffect(() => {
    // refresh() explícito (após criar/editar/pagar algo) é a única coisa que
    // invalida o cache — não sabemos o que mudou, então limpa tudo em vez de
    // arriscar mostrar um mês desatualizado.
    if (refreshKey !== lastRefreshKeyRef.current) {
      cacheRef.current.clear();
      lastRefreshKeyRef.current = refreshKey;
    }

    const key = `${month}-${year}`;
    activeKeyRef.current = key;
    const cached = cacheRef.current.get(key);
    if (cached) {
      setPayables(cached.payables);
      setCategories(cached.categories);
      setSummary(cached.summary);
      setUpcoming(cached.upcoming ?? []);
      setBills(cached.bills ?? []);
      setPrevSummary(cached.prevSummary ?? null);
      setInsights(cached.insights ?? []);
      setHistory(cached.history ?? []);
      setLoading(false);
      // `cached.upcoming === undefined` cobre tanto uma entrada de
      // sessionStorage de antes desta mudança quanto uma entrada gravada
      // enquanto o usuário estava em outra rota (extras puladas de
      // propósito, ver fetchFinance) — só vale buscar agora se a rota atual
      // É o dashboard, senão ficaria refazendo a mesma checagem à toa a
      // cada render enquanto o usuário estiver em outra tela.
      const missingExtras = needsDashboardData && cached.upcoming === undefined;
      if (Date.now() - (cached.fetchedAt ?? 0) > STALE_TTL_MS || missingExtras) {
        fetchFinance(key, month, year, { silent: true });
      }
      return;
    }

    fetchFinance(key, month, year);
  }, [month, year, refreshKey, needsDashboardData, fetchFinance]);

  // Revalida em segundo plano ao voltar pra aba (padrão comum em SaaS: Gmail,
  // Slack) — cobre "deixei aberta e o cron/webhook mudou algo" sem esperar o
  // usuário mexer em mês/ano ou fazer uma mutação local. Listener + dedup de
  // visibilitychange/focus disparando juntos moram no hook compartilhado
  // (também usado por BankAccountsPage, issue #116); `revalidatingKeysRef`
  // dentro de `fetchFinance` continua sendo uma 2ª camada, pro caso de troca
  // rápida de mês coincidir com um foco de aba.
  useRevalidateOnFocus(
    useCallback(async () => {
      const key = `${month}-${year}`;
      const cached = cacheRef.current.get(key);
      // Sem entrada nenhuma: o efeito de cima já cuida na próxima renderização.
      if (cached && Date.now() - (cached.fetchedAt ?? 0) > STALE_TTL_MS) {
        await fetchFinance(key, month, year, { silent: true });
      }
    }, [month, year, fetchFinance])
  );

  return (
    <FinanceContext.Provider
      value={{
        payables,
        categories,
        summary,
        loading,
        refresh,
        upcoming,
        bills,
        updateBills,
        prevSummary,
        insights,
        history,
      }}
    >
      {children}
    </FinanceContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const useFinance = () => useContext(FinanceContext);
