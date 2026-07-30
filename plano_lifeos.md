# LifeOS — o que foi feito e o que falta

> Registro da leva de trabalho que começou com "dá pra usar o Meu Pluggy pra uso pessoal?"
> e terminou com o dashboard repaginado em torno de "pra onde vai meu dinheiro".
> Última atualização: 29/07/2026.

## Contexto

O LifeOS era um app de lançamento manual: você digitava contas a pagar e o dashboard
mostrava esse checklist. Nesta leva ele ganhou sincronização bancária real (Itaú, Nubank,
Inter via Pluggy) e um dashboard que usa esse histórico para responder "pra onde vai meu
dinheiro", com insights comparativos mês a mês.

Tudo já está commitado e em produção (Render + Vercel). Nada listado aqui como "feito"
depende de deploy adicional.

---

## O que foi feito

### 1. Uso pessoal via Pluggy, sem custo (`f070a38`)

A Pluggy não atende caso de uso pessoal no plano comercial (R$ 2.500/mês). A solução —
confirmada contra a API real, não só documentação — é o conector **MeuPluggy**: você conecta
os bancos em `meu.pluggy.ai` e uma Development Application do dashboard (grátis, mesmo com
trial expirado) acessa os dados via um conector proxy.

- 3 bancos conectados (Itaú, Nubank, Inter), sincronizando via webhook em produção.
- `describe_item` deriva o nome da conexão das accounts do item (o conector só devolve
  `"MeuPluggy"` como nome, então isso teria que vir de outro lugar). `PATCH /bank-accounts/{id}`
  permite renomear à mão.
- Setup completo documentado no `CLAUDE.md`, seção "Uso pessoal via conector MeuPluggy".

### 2. Faturas de cartão: janela de payable acionável (`5e838f6`)

A Pluggy devolve o histórico inteiro do cartão e, em alguns bancos (Inter), também faturas
**projetadas** de parcelamento — um cartão veio com 48 faturas indo até 2027. Gerar `Payable`
para todas poluía a lista em duas pontas: fatura antiga não conciliada ficava "vencida" pra
sempre, e projeção futura mostrava valor que ainda ia mudar.

- `is_in_payable_window`: só cria `Payable` se a fatura vence no mês atual ou no seguinte.
  A fatura continua salva como `CreditCardBill` — o histórico não se perde, só não vira
  obrigação a pagar.
- **Limpeza feita em produção** (script one-off, não faz parte do código): 41 payables
  fantasma viraram `PAID` (foram realmente pagos), 14 apagados (valor zero ou projeção fora
  da janela). R$ 14.139,83 de dívida que não existia sumiu do dashboard.

### 3. Classificação de transação corrigida (`a6c15fa`, `9d1294d`)

Achado grave: o tipo (INCOME/EXPENSE) era inferido do **sinal** do valor, mas o sinal não é
consistente entre tipos de conta — em cartão de crédito a compra vem **positiva**. Mais da
metade das 2023 transações importadas estava com o tipo invertido (1343 INCOME / 683 EXPENSE
gravados, quando a Pluggy reportava 1584 DEBIT / 439 CREDIT).

- `_transaction_type` agora deriva do campo `type` da Pluggy (DEBIT/CREDIT), com fallback pro
  sinal quando o campo não existe (extrato CSV).
- `pluggy_category_map.py`: mapeia as ~61 categorias que a Pluggy já atribui para as
  categorias do usuário — antes o campo vinha e era ignorado, 100% das transações ficavam
  sem categoria mesmo 96% vindo classificadas da API.
- 5 categorias novas: Saúde, Compras, Taxas, Seguros, **Transferências** (PIX/TED a terceiros
  — é gasto real, mas sem categoria ficava invisível no "gasto por categoria": ~21% do
  extrato).
- `is_transfer`: marca dinheiro que só muda de lugar (quitação de fatura, transferência
  entre as próprias contas, aporte em investimento). Excluído dos totais de gasto — senão a
  mesma grana conta duas vezes (a compra no cartão **e** a quitação da fatura).
- **Backfill aplicado em produção**: 2023 transações reclassificadas contra a API da Pluggy.

### 4. Backend: gasto por categoria de verdade (`b3332cc`)

O campo que existia (`total_transactions`) somava receita e despesa no mesmo número — não
respondia "quanto gastei". E `budget_used_pct` usava payables, não transações, então gasto de
cartão importado do banco não movia o orçamento.

- `CategorySummary.total_expenses` + `transaction_count`, só de gasto real (EXPENSE, sem
  transferência).
- `budget_used_pct` passa a reagir ao gasto real.
- Ordenação por gasto (antes era por payables — categoria só-transação afundava no fim).
- `OVERDUE` volta a contar em `total_pending` (sumia de todos os totais).
- Categoria com orçamento definido e zero movimento aparece (antes desaparecia).
- **`insight_service.py`** (novo): regras puras — variação por categoria vs mês anterior,
  categoria nova, maior gasto do mês, ritmo vs mesmo trecho do mês anterior (com projeção),
  orçamento perto/estourado. Limiar de R$ 50 e 10% pra não virar ruído. `GET /insights`.
- **`GET /transactions`**: filtro por categoria (+ "sem categoria"), exclusão de
  transferência, paginação. Sustenta o drill-down do dashboard.
- **`GET /summary/history`**: 2 queries no intervalo inteiro em vez de `get_summary` num loop
  mês a mês (era `3 × months` queries).
- 202 testes backend (eram 122 no início da sessão).

### 5. Frontend: dashboard novo (`81499dc`)

O dashboard antigo só mostrava payables — as transações reais não tinham nenhuma superfície
na tela, e "Sem categoria" misturava faturas de cartão com gasto de verdade.

- **Herói** "Gasto do mês" com delta vs mês anterior.
- **Faixa de insights** (cards horizontais, `GET /insights`) — a entrega que foi pedida
  explicitamente ("você gastou R$ 200 a menos em tal categoria").
- **Gasto por categoria** em barras clicáveis, substituindo o donut — ordenado por gasto real,
  leva ao drill-down.
- **Tendência**: primeiro gráfico de série temporal do app (`recharts`, já instalado mas nunca
  usado pra isso), consumindo `/summary/history`.
- **Drill-down por categoria** (`/categoria/:id`, incluindo "Sem categoria" via slug): lista
  as transações que compõem o total. Validado com dado real — inclusive um bug pego só na
  tela (drill-down somava uma transação de estorno/INCOME que o card não contava; corrigido
  filtrando `type=EXPENSE`).
- **Compromissos** (payables) isolados visualmente, com aviso explícito de que não entram no
  gasto — evita números que parecem contraditórios na mesma tela.
- **Fundação de UI**: `src/lib/format.js` (substituiu 4 cópias do formatador de moeda),
  `components/ui/` (Card, StatCard, DeltaBadge, EmptyState, Skeleton, CategoryDot).
  `Toast`/`ConfirmModal`/`StatusBadge` ganharam tema claro (eram dark-only).

---

## Lições operacionais (documentadas no `CLAUDE.md`)

- **Não existe ambiente de desenvolvimento isolado.** O `.env` local aponta pro banco de
  produção (Neon), e o webhook da Pluggy aponta pro backend de produção (Render). Corrigir um
  bug de sync localmente **não** protege os dados — quem recebe o webhook e o cron diário é o
  Render, com o código que estiver deployado lá.
- **Ordem obrigatória quando um bug de sync é corrigido:** deploy primeiro, limpeza de dados
  depois. Na ordem inversa, o próximo evento da Pluggy recria o problema.
- A instância do Render é **free tier** e hiberna por inatividade (delay de 50s+ ao acordar) —
  o webhook da Pluggy pode não chegar a tempo se o serviço estiver dormindo.

---

### 6. Alias editável de cartão de crédito & Indicação de transferências no Extrato

- **Alias editável de cartão**: Adicionado o campo `custom_card_name` ao modelo `CreditCardBill`, migration Alembic `d9e0f1a2b3c4` e rota `PATCH /credit-card-bills/{id}`. Ao renomear um cartão no Dashboard (edição inline), todas as faturas e títulos de `Payable` correspondentes daquele cartão são atualizados automaticamente.
- **UI de transferências no Extrato (`/transactions`)**: Extrato atualizado com um card visual de total de transferências, badge `🔄 Transferência` azul/indigo para movimentações internas (aportes, PIX próprio, fatura) e filtro dedicado para isolar ou ocultar transferências.

---

## O que ainda falta

Por ordem aproximada de impacto:

### Pendências de produto

- **Metas de objetivo/poupança** (ex: "faltam R$ 2.300 pra reserva de emergência") — precisa de model novo, não existe hoje. `Budget` (teto por categoria/mês) já existe e já está integrado ao dashboard.
- **Repaginação completa no app inteiro (Desktop e Mobile)** — repaginação completa de Contas (`/payables`), Extrato (`/transactions`), Contas Bancárias (`/banks`) e Configurações (`/settings`) em torno do novo design system.

### Verificações não feitas

- **Cron Job do Render** — nunca foi confirmado se existe. O dashboard do Render (visto nesta sessão) só lista o web service `lifeos-backend`, sem Cron Job separado. Se não existir, `daily_sync` (geração de payables recorrentes do mês + push de vencimento) **nunca roda sozinho** — só o webhook da Pluggy dispara sync, e só de dados de banco, não de recorrentes manuais nem de push.
- **Categoria "Services" da Pluggy** — ficou de fora do mapeamento (14 transações no backfill, volume baixo, nome vago demais pra decidir destino sem mais contexto).

### Dívidas técnicas menores

- Bundle do frontend passou de 500kB depois do `recharts` ganhar mais uso — vite avisa mas não quebra o build. Não é urgente, mas code-splitting seria a correção natural se crescer mais.
- Os 2 `React Hook useEffect has a missing dependency` (`PayablesPage`, `RecurringPayablesPage`) são anteriores a esta leva e não foram tocados.

---

## Referência rápida

- **Backend produção:** `https://lifeos-backend-sa9n.onrender.com`
- **Frontend produção:** `https://life-os-murex-psi.vercel.app`
- **Setup Pluggy pessoal:** `CLAUDE.md`, seção "Uso pessoal via conector MeuPluggy"
- **Commits desta leva** (mais antigo → mais novo):
  `f070a38` → `5e838f6` → `a6c15fa` → `9d1294d` → `b3332cc` → `81499dc`
- **Testes:** 202 backend (`cd backend && pytest`), suíte frontend mínima (`npm test` —
  só `StatusBadge`, sem cobertura de página).
