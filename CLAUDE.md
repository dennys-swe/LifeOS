# CLAUDE.md

Este arquivo orienta o Claude Code (claude.ai/code) ao trabalhar neste repositório.

## Visão Geral do Projeto

LifeOS é um SaaS multi-tenant de gestão financeira pessoal focado em **contas a pagar, faturas de cartão e gastos** (não é mais só uso pessoal single-tenant — cada usuário cria conta e só enxerga seus próprios dados). Stack: FastAPI no backend e React + Vite + Tailwind CSS v4 no frontend, com react-router. Infraestrutura de produção: PostgreSQL no Neon.tech, backend no Render, frontend na Vercel.

Autenticação via **fastapi-users** (JWT Bearer). Contas bancárias e faturas de cartão são sincronizadas via **Pluggy** (Open Finance BR) — cada usuário conecta seu próprio banco.

## Comandos

### Backend

```bash
# Servidor de desenvolvimento
uvicorn app.main:app --reload

# Rodar todos os testes
cd backend && pytest

# Rodar um arquivo de teste específico
cd backend && pytest tests/test_recurring.py

# Rodar um teste por nome
cd backend && pytest tests/test_recurring.py -k "test_generate_no_duplicate"

# Aplicar migrations
cd backend && alembic upgrade head

# Criar nova migration
cd backend && alembic revision -m "descricao"  # escrever à mão; ver nota de multi-tenant abaixo

# Rodar o job de sync diário manualmente
cd backend && python -m app.jobs.daily_sync
```

O backend exige um arquivo `backend/.env` com `DATABASE_URL`, `SECRET_KEY` (JWT), `CORS_ORIGINS`, `CRON_SECRET`, `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET` e as chaves VAPID (ver `.env.example`). Testes usam SQLite em memória — sem necessidade de banco real, e não passam pelo Alembic (schema vem direto dos models via `Base.metadata.create_all`).

> ⚠️ **Não existe ambiente de desenvolvimento isolado.** O `backend/.env` local aponta para o **banco de produção** (Neon), e o webhook da Pluggy está registrado apontando para o **backend de produção** (Render). Duas consequências que já causaram problema real:
> - Rodar o backend local escreve em dados de produção.
> - **Corrigir lógica de sync localmente não protege os dados**: quem recebe o webhook (`item/created` ao conectar um banco) e o cron diário é o Render, com o código que estiver deployado. Ao consertar algo que o sync grava errado, **deploy primeiro, limpeza dos dados depois** — na ordem inversa, o próximo evento da Pluggy recria o problema.

Config central em `app/core/config.py` (`pydantic-settings`) — nunca usar `os.getenv` solto em código novo, sempre `from app.core.config import settings`.

### Frontend

```bash
cd frontend && npm run dev    # servidor de desenvolvimento
cd frontend && npm test       # vitest
cd frontend && npm run lint   # eslint
cd frontend && npm run build  # build de produção
```

O frontend lê `VITE_API_URL` do ambiente (padrão: `http://localhost:8000`).

## Arquitetura

### Backend (`backend/`)

Camadas FastAPI seguindo o padrão: **Router → Service → SQLAlchemy ORM → PostgreSQL**.

- `app/main.py` — setup do app, CORS (restrito via `settings.cors_origins_list`) e registro de todos os routers, incluindo as rotas de auth do fastapi-users (`/auth/jwt/*`, `/auth/register`, `/users/*`). A rota raiz usa `@app.api_route` para suportar HEAD (uptime monitoring).
- `app/api/endpoints/` — handlers finos: validam, chamam o service e retornam. **Todo endpoint de dado exige `user: User = Depends(current_active_user)`** e repassa `user.id` ao service.
- `app/services/` — lógica de negócio. Cada domínio tem seu service (`recurring_service`, `reconciliation_service`, `summary_service`, `bill_service`, `bank_sync_service`, etc.). **Toda função de service que lê/escreve dados recebe `user_id` e filtra por ele** — nunca fazer `select(Model)` sem `.where(Model.user_id == user_id)`.
- `app/models/` — ORM SQLAlchemy. **Toda tabela de dados tem `user_id` (FK `users.id`, ondelete=CASCADE)**, exceto `users`.
- `app/schemas/` — schemas Pydantic v2 (usar `model_dump`, `ConfigDict`, `from_attributes=True`).
- `app/core/config.py` — `Settings` (pydantic-settings), fonte única de env vars.
- `app/core/users.py` — núcleo do fastapi-users: `SyncSQLAlchemyUserDatabase` (adapter próprio sobre a `Session` sync do projeto — **não** usa `fastapi-users-db-sqlalchemy`, que exige async), `UserManager` (semeia as 6 categorias padrão no `on_after_register`), `auth_backend` (JWT Bearer), `current_active_user` (dependency usada em todos os endpoints).
- `app/db/database.py` — engine (`pool_pre_ping=True`) + session factory. SSL automático para PostgreSQL. `get_db()` é a dependency FastAPI.
- `app/jobs/daily_sync.py` — job de sync diário (`python -m app.jobs.daily_sync`), pensado para rodar como Render Cron Job. Por usuário: sincroniza contas Pluggy, gera payables do mês a partir dos recorrentes, dispara push de contas vencendo. Também exposto via `POST /jobs/daily-sync` protegido por header `X-Cron-Secret`.
- `alembic/versions/` — migrations em ordem cronológica.

**Testes** (`backend/tests/`) usam `pytest` com SQLite em memória via `conftest.py`, que sobrescreve `get_db` **e** `current_active_user` (fixtures `user`/`other_user`) no `TestClient`. Para testar o fluxo real de auth (register/login/JWT) sem overrides, ver `tests/test_auth.py` (fixture `raw_client`).

**Compatibilidade SQLite:** `summary_service` agrega em Python (não SQL `GROUP BY`) para funcionar nos testes. Nunca usar `func.date_trunc` ou funções PostgreSQL-only nos services.

**Ordem de registro de rotas:** endpoints com path literal (ex: `/generate`, `/upcoming`, `/notify`, `/suggestions`) devem ser registrados **antes** de `/{id}` para evitar que o FastAPI interprete strings como UUIDs.

**Multi-tenancy — histórico da migração:** duas revisions (`e8a74d06536e` add users + `user_id` nullable, `ed1c2a45d964` backfill + NOT NULL + uniques compostas) documentam o runbook de produção: deploy → dono se registra via `/auth/register` (vira o primeiro usuário) → roda a segunda revision. Qualquer nova migration que mexa em tabelas de dados já assume `user_id NOT NULL`.

### Integração Pluggy (Open Finance)

- `app/services/pluggy_client.py` — autentica com `PLUGGY_CLIENT_ID`/`SECRET` (credenciais da aplicação, cache de api_key em memória). O isolamento por usuário vem de `bank_accounts.user_id`, não de um campo da Pluggy (o SDK instalado não expõe `clientUserId` no `ConnectTokenRequest`).
- `app/services/pluggy_category_map.py` — mapeia as ~61 categorias que a Pluggy atribui (`Groceries`, `Gas stations`, ...) para as 10 categorias padrão do usuário, e define quais são **transferência**. Mapa explícito de propósito: categoria nova que a Pluggy inventar fica sem categoria em vez de ser adivinhada errado, e `Transaction.external_category` guarda o valor cru pra descobrir o que completar.
- `app/services/bank_sync_service.sync_account` — sincroniza transações (dedup por `(user_id, source="pluggy:{tx_id}")`) e, para contas `type == "CREDIT"`, também as faturas via `bill_service`. Usa `*_without_preload_content` + `json.loads` como workaround de um bug de validação Pydantic do SDK (`CreditCardMetadata.payeeMCC`); o mesmo padrão foi replicado para `BillApi.bills_list_without_preload_content`. Ao final, roda `suggest_reconciliation` + `auto_reconcile_confident_matches` sobre as transações recém-importadas.
- `app/services/bill_service.py` — upsert de `CreditCardBill` por `(user_id, external_id)` e geração/atualização automática do `Payable` correspondente (nunca atualiza um payable já `PAID`).
- Faturas só existem em conexões Open Finance Regulado — falha ao buscar degrada para lista vazia (não derruba o sync de transações), mas **loga em stderr** (`[bank_sync] bills indisponíveis ...`). Se a geração automática de `Payable` de fatura parar de acontecer, esse log é o primeiro lugar a olhar.
- `app/api/endpoints/webhooks.py` — `POST /webhooks/pluggy` (público, sem auth) dispara `run_sync_job` em background para o item afetado nos eventos `item/created|updated` e `transactions/created|updated`. A URL é registrada no dashboard da Pluggy, não via código (`get_connect_token` não passa `ItemOptions.webhook_url`).

#### Uso pessoal via conector "MeuPluggy" (sem plano comercial)

A Pluggy **não atende caso de uso pessoal** no plano comercial (o plano inicial é R$ 2.500/mês, até 500 conexões). Para uso pessoal, a própria Pluggy oferece o **MeuPluggy** (https://meu.pluggy.ai, repo de docs em https://github.com/pluggyai/meu-pluggy): você conecta seus bancos lá e a aplicação de desenvolvimento acessa esses dados via um conector proxy, de graça.

Setup (todo no dashboard/navegador, **não** em código):

1. Conectar os bancos em https://meu.pluggy.ai.
2. Em https://dashboard.pluggy.ai, criar uma **Development Application** → gera o `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET`.
3. Em Customização, habilitar o conector **MeuPluggy** (id `200`, `type=PERSONAL_BANK`, `oauth=True`).
4. Registrar a webhook URL apontando para `<backend>/webhooks/pluggy`.
5. No LifeOS, Contas Bancárias → Conectar → autorizar via OAuth — **uma vez por banco** conectado no MeuPluggy (banco, não conta).

Fatos verificados empiricamente contra a API (2026-07-29, item real do dono):

- **O trial expirado do dashboard não bloqueia a API** — `AuthApi.auth_create` segue devolvendo api_key e as leituras funcionam, como o README do meu-pluggy promete.
- **As faturas de cartão funcionam pelo proxy do MeuPluggy** — `BillApi` devolveu 15 e 14 faturas reais (com `dueDate`/`totalAmount`) para os dois cartões do item. A automação de `Payable` de fatura não é bloqueada pelo uso pessoal.
- Com só o MeuPluggy habilitado, **todo item volta com `connector.name == "MeuPluggy"`** — inútil como rótulo. Daí `describe_item`.
- **Um item do MeuPluggy agrega várias accounts, possivelmente de instituições diferentes** (uma conta corrente + cartões de bandeiras/emissores distintos vieram no mesmo item). Nomear o item com uma account só seria enganoso — `describe_item` lista todas (BANK primeiro), truncando com `(+N)` acima de 100 chars.
- **É um item por banco conectado no MeuPluggy**, não um item para tudo: o README do meu-pluggy é explícito ("once per connected bank... bank, not bank account"). Quem tem 3 bancos lá precisa rodar o Conectar 3 vezes no LifeOS, gerando 3 `BankAccount` — daí a importância de `describe_item`/rename.
- `marketingName` vem **sempre `None`** no proxy; o nome útil está em `name`.

### Frontend (`frontend/src/`)

SPA roteada com **react-router** (`BrowserRouter`).

- `App.jsx` — árvore de rotas: `/login`, `/register` (públicas) e um grupo protegido por `ProtectedLayout` (`/`, `/categoria/:id`, `/payables`, `/transactions`, `/banks`, `/settings`).
- `components/ProtectedLayout.jsx` — gate de auth (`useAuth()`; redireciona para `/login` se não autenticado) **acima** do `FinanceProvider`. Também é dono do estado `selectedMonth/Year`/`payablesFilter`, repassado às páginas via `useOutletContext()`.
- `context/AuthContext.jsx` — `login`/`register`/`logout`, token em `localStorage`. Login é form-encoded (`username`/`password`) — peculiaridade do fastapi-users, não JSON.
- `services/api.js` — axios singleton com interceptor de request (injeta `Authorization: Bearer`) e de response (401 → limpa token e redireciona para `/login`).
- `context/FinanceContext.jsx` — estado global compartilhado. Faz 3 chamadas em paralelo (`/payables`, `/categories`, `/summary`) e expõe `payables`, `categories`, `summary`, `loading`, `refresh()`. Re-dispara quando `month`, `year` ou `refreshKey` mudam.
- `pages/DashboardPage.jsx` — dashboard focado em **contas, faturas e gastos** (StatCards "A vencer", "Vencidas", "Faturas do mês", "Pago no mês"; gastos por categoria; faturas de cartão; orçamento). Não mostra mais fluxo de caixa (entrou/saiu) — esse dado ainda existe no backend (`SummaryResponse.total_income/total_expenses/balance`) por compatibilidade, mas o frontend não consome mais.
- `pages/PayablesPage.jsx` — lista de contas com filtros, exclusão otimista com undo via toast; embute `RecurringPayablesPage` como aba "Recorrentes".
- `pages/RecurringPayablesPage.jsx` — CRUD de recorrentes + botão "Gerar para este mês" + bloco de sugestões de recorrentes detectadas automaticamente (`GET /recurring-payables/suggestions`), com aceitar/descartar (descarte é só local, não persiste).
- `pages/CategoryDetailPage.jsx` — drill-down de uma categoria: lista as transações que compõem o total do card do dashboard (inclui "Sem categoria" via slug).
- `pages/BankAccountsPage.jsx` — fluxo Pluggy Connect (widget via CDN) + lista de contas conectadas + sugestões de conciliação (as faturas de cartão são listadas no `DashboardPage`, não aqui). Ao conectar, envia só `external_id` (o backend deriva o nome); clicar no nome da conta habilita rename inline (`PATCH`, otimista).
- `pages/SettingsPage.jsx` — abas Regras / Categorias / **Notificações** (toggle que assina push via `Notification.requestPermission()` + `pushManager.subscribe()`, usando a chave de `GET /push-subscriptions/vapid-public-key`).
- `components/FabModal.jsx` — FAB que abre modal para criar payable ou transação.
- `components/Sidebar.jsx` — nav via `NavLink`; rodapé com e-mail do usuário e logout.

**Invariante de datas:** `due_date` trafega e é armazenada como string `YYYY-MM-DD`. **Nunca** construir `new Date(due_date)` — o GMT offset desloca a data um dia. Sempre usar `.split('-')`, `localeCompare` ou comparação direta de strings.

**Exclusão com Undo:** remoção é otimista — item sai do estado imediatamente e um `setTimeout` de 5s dispara o `DELETE` real. O botão "Desfazer" no Toast cancela o timeout e restaura o item sem chamada de API.

**Estado compartilhado:** nunca buscar `/payables` ou `/categories` diretamente dentro de páginas. Usar `useFinance()` do FinanceContext. Chamar `refresh()` após qualquer mutação (create, update, delete, pay).

### Modelos e Domínios

| Modelo | Descrição |
|---|---|
| `User` | Conta de usuário (fastapi-users): email, hashed_password, is_active/superuser/verified |
| `Payable` | Conta a pagar. `user_id` obrigatório. FKs nullable: `recurring_payable_id` (ondelete=SET NULL), `transaction_id` (ondelete=SET NULL) |
| `RecurringPayable` | Template de recorrência (title, amount, day_of_month, active, start_date/end_date). `user_id` obrigatório |
| `Transaction` | Transação de extrato bancário. `user_id` obrigatório; índice composto `(user_id, source)` para dedup do sync Pluggy. `is_transfer` exclui dos totais de gasto; `external_category` guarda a categoria crua da Pluggy |
| `Category` | Categoria com cor (color_hex) e `kind` (`EXPENSE`/`INCOME`), por usuário. `UniqueConstraint(user_id, name)`. Seed de 16 categorias padrão no registro (12 de gasto + 4 de receita) |
| `CategoryRule` | Regra de categorização por keyword (armazenada em UPPERCASE). `user_id` obrigatório |
| `Budget` | Orçamento mensal por categoria. `UniqueConstraint(user_id, category_id, month, year)` |
| `BankAccount` | Conta bancária conectada via Pluggy (`external_id` = itemId). `user_id` obrigatório |
| `CreditCardBill` | Fatura de cartão. `UniqueConstraint(user_id, external_id)`; `payable_id` liga à conta a pagar gerada automaticamente. `status` distingue `CLOSED` (oficial, da Bills API) de `OPEN` (ciclo corrente reconstruído das transações — não gera `Payable`). `custom_card_name`/`custom_color_hex` são do **cartão**, propagados a todas as faturas do mesmo `pluggy_account_id` |
| `PushSubscription` | Subscription VAPID para push notifications. `user_id` obrigatório; `endpoint` continua unique global (é por device) |

### Lógica de Negócio Crítica

**`generate_for_month` (recurring_service):** para cada `RecurringPayable` ativo **do usuário**, calcula `due_date = date(year, month, min(day_of_month, last_day_of_month))` e cria um `Payable` somente se ainda não existir um com mesmo `recurring_payable_id` no mês (deduplicação, sempre escopada por `user_id`).

**`build_keyword_map` (category_rule_service):** retorna `dict[keyword, category_id]` ordenado por `priority DESC`, escopado por `user_id`. Usa first-occurrence para preservar a prioridade mais alta quando há duplicatas de keyword.

**`suggest_reconciliation` (reconciliation_service):** para cada transação EXPENSE do usuário, busca payables PENDING do mesmo usuário com `amount` dentro de 5% e `due_date` dentro de ±7 dias. Confidence scoring: 1.0 (exato), 0.8 (valor exato, data ±7d), 0.6 (valor ±5%, data exata), 0.5 (ambos tolerantes).

**`auto_reconcile_confident_matches` (reconciliation_service):** confirma automaticamente sugestões com confidence 1.0 **somente quando o match é único** (nem o payable nem a transação aparecem em mais de uma sugestão exata) — evita reconciliar errado em caso de empate. Rodado ao fim do sync Pluggy. As sugestões que sobram aparecem em `/banks`, para confirmação manual.

**`upsert_bill` (bill_service):** upsert de `CreditCardBill` por `(user_id, external_id)`; gera um `Payable` na primeira sincronização e atualiza valor/vencimento nas seguintes **só se o payable ainda estiver PENDING** (nunca sobrescreve valor/vencimento de um já pago). O **título** é exceção: é recalculado sempre, inclusive em payable pago, porque é só rótulo — payables criados antes de `card_name` ser gravado ficaram como `Fatura {nome da conexão}` e, com o MeuPluggy, dois cartões do mesmo mês viravam títulos idênticos.

**`PayableResponse.origin` (`MANUAL`/`BILL`/`RECURRING`) e `is_estimated`:** atributos calculados em `annotate_origin`, não colunas — a origem já está implícita no `recurring_payable_id` e no `CreditCardBill.payable_id` que aponta de volta. A tela precisa deles para **não** oferecer editar/excluir em conta gerada pelo sync (o próximo sync recria e sobrescreve) e para avisar que fatura aberta ainda muda de valor. As faturas são resolvidas em uma consulta só, senão a listagem faz N+1.

**`is_in_payable_window` (bill_service):** o `Payable` só é **criado** se o vencimento da fatura cair no mês atual ou no seguinte. Motivo: a Pluggy devolve o histórico inteiro do cartão e, em alguns bancos, também faturas **projetadas** de parcelamento — um cartão do Inter veio com 48 faturas, a mais distante vencendo ~1 ano à frente. Sem a janela, fatura antiga não conciliada fica `PENDING` pra sempre (aparece como "vencida" que não se deve) e projeção futura polui meses à frente com valor que ainda vai mudar. Fora da janela a fatura **continua salva** como `CreditCardBill` — o histórico segue disponível para análise (`detect_recurring_candidates`, comparação de categorias), só não vira obrigação a pagar. A janela filtra apenas a criação: payable que já existe continua sendo mantido em sincronia.

**Fatura em aberto (`open_bill_service` + `CreditCardBill.status`):** a Bills API só publica a fatura **depois** do fechamento, e o atraso varia por banco (Nubank e Itaú só expuseram entre 0 e 7 dias antes do vencimento; o Inter projeta com quase um ano de antecedência). No intervalo o dashboard ficava sem nenhuma informação da fatura corrente, então o sync reconstrói o ciclo aberto a partir das transações e salva como `CreditCardBill` com `status=OPEN`. Quando a fatura oficial chega, o **mesmo registro** vira `CLOSED` (o lookup por `(pluggy_account_id, mês)` de `upsert_bill` reaproveita a linha, sem duplicar). Fatura **aberta também gera `Payable`** (a obrigação existe desde que o ciclo abre), com o valor atualizado a cada sync enquanto o payable estiver `PENDING`. Só valia para `CLOSED` antes, mas a conta então só aparecia poucos dias antes do vencimento e o dono lançava na mão — gerando duplicata quando a automática chegava (18 lançamentos, R$ 9.378, no histórico real).

Fatos verificados contra a API (2026-08-04, valores reais conferidos pelo dono):

- **`account.balance` não serve como fatura.** É o limite consumido e a semântica varia: no Nubank ele soma o ciclo seguinte e as parcelas ainda não cobradas (R$ 787,16 contra R$ 588,37 de fatura real); na Luiza coincide com a fatura. Foi o que a tela do meu.pluggy.ai mostrava.
- **`creditCardMetadata.billForecastDate`** (ex: `"2026-08"`) é a fonte mais confiável de qual competência a pendência vai cair — mas o Itaú rotula pelo **mês da compra**, mandando lançamentos de 15–25/07 como `2026-07` com a fatura de julho já paga; pendência sem `billId` cuja competência já fechou rolou para o ciclo seguinte.
- **Parcelamento vem em dois formatos incompatíveis.** O Nubank só emite a parcela do ciclo corrente (as futuras precisam ser projetadas); Itaú/Luiza já emitem todas as parcelas futuras como pendências **datadas no vencimento** em que serão cobradas — projetar nesse caso conta em dobro, e a mesma parcela ainda reaparece depois de faturada. Projetar a partir de cada parcela conhecida em vez da mais recente triplica o valor.
- **Pagamento de fatura nem sempre cai na categoria certa:** `"PAGAMENTO COM SALDO"` (Itaú/Luiza) vem como `Transfers`, mesma categoria de créditos legítimos que abatem a fatura (`"Encerramento de dívida"`). Detecção usa categoria **e** descrição. O pagamento fica registrado na fatura **seguinte** — somá-lo zeraria o ciclo novo.
- Compras em moeda estrangeira exigem `amountInAccountCurrency` (o `amount` vem em USD).

Precisão medida: Nubank **exato** (R$ 588,37), Luiza +11% (anuidade que é estornada por um crédito mensal), Itaú −6,4% (cartão em refinanciamento — encargos de rotativo só são calculados pelo banco no fechamento, nenhuma soma de transações os antecipa).

**Tipo da transação vem do campo `type` da Pluggy, nunca do sinal do valor** (`_transaction_type` em `bank_sync_service`). O sinal **não** é consistente entre tipos de conta: em conta corrente a saída vem negativa, mas em **cartão de crédito a compra vem positiva** (`+15.99 type=DEBIT ANUIDADE`, verificado na API). Inferir pelo sinal marcava toda compra de cartão como receita — nos dados reais do dono, mais da metade das transações ficou invertida (1343 INCOME / 683 EXPENSE, quando a Pluggy reporta 1584 DEBIT / 439 CREDIT). Sem `type`, cai no sinal, que é correto para conta corrente.

**Transferência (`Transaction.is_transfer`)** marca dinheiro que só muda de lugar: quitação de fatura, transferência entre as próprias contas (`Same person transfer`), aporte em investimento. `summary_service` **exclui** transferências dos totais e do por-categoria — senão a mesma grana conta duas vezes (a compra no cartão **e** a quitação da fatura). Decisões explícitas: PIX/TED/boleto **para terceiros é gasto** (o dinheiro saiu de vez) e vai para a categoria `Transferências` — é gasto sem natureza de consumo, e deixá-lo sem categoria escondia ~21% das transações do "gastos por categoria"; aporte em investimento **não é** gasto (o dinheiro continua seu). `recurring_detection` também exclui transferências (219 `Same person transfer` dominavam as sugestões). Já a **conciliação inclui** a quitação de fatura mesmo sendo `type=CREDIT` do lado do cartão (`_reconcilable`) — é a única ponta disponível quando a conta pagadora não está conectada.

**A categoria da Pluggy não basta para reconhecer quitação de fatura.** `is_transfer` também casa a **descrição** (`pagamento de fatura` / `fatura paga`): nos dados reais do dono, 13 quitações vieram com `category="Transfers"` genérico em vez de `Credit card payment`, e por isso contavam como gasto — R$ 2.714,13 de contagem dupla, 6,4% do gasto de jun+jul/2026.

**Categoria tem tipo (`Category.kind`: `EXPENSE`/`INCOME`).** Antes não existia nenhuma categoria de receita, então dinheiro recebido caía em `Transferências` — categoria criada para PIX **enviado** (202 lançamentos, R$ 58.542,65). Consequências no código:

- `category_name_for(pluggy_category, is_income)` é **direcional**: a mesma categoria da Pluggy significa coisas opostas conforme o dinheiro entra ou sai (`Transfer - PIX` enviado é gasto, recebido é receita). Entrada que só casa com categoria de despesa vai para `Outras receitas` — a Pluggy classifica pelo **estabelecimento**, não pela direção, então repasse e estorno são indistinguíveis ali (foi assim que a renda semanal da Uber, `Taxi and ride-hailing`, foi parar em `Transporte`).
- `_category_for_direction` (bank_sync_service) é a trava final: regra de keyword não sabe direção, e uma regra `UBER -> Renda extra` casaria também com uma corrida paga pelo usuário. Categoria cujo `kind` não bate com o tipo da transação é **descartada** — sem categoria é melhor que categoria errada, porque fica visível e corrigível.

**Regra de categorização vale retroativamente** (`apply_rule_to_existing`, chamada no `POST /category-rules`). O sync deduplica pelo id da Pluggy e pula transação existente, então sem isso criar uma regra não mudava nada na tela e parecia quebrado. A regra sobrescreve categoria anterior (é a fonte da verdade), mas nunca cruza a direção do dinheiro. O filtro usa `is_distinct_from` — `!=` deixaria de fora justamente os sem categoria, porque `NULL != valor` é `NULL` em SQL. O endpoint devolve `applied_count` para a tela poder dizer quantos lançamentos mudaram.

**`detect_recurring_candidates` (recurring_detection_service):** agrupa transações EXPENSE por descrição normalizada (maiúsculas, sem dígitos); exige ≥3 meses distintos, valor dentro de ±10% da mediana e dia do mês com desvio ≤3 do modo. Exclui títulos que já têm `RecurringPayable` cadastrado.

### Endpoints da API

| Método | Path | Descrição |
|--------|------|-----------|
| `GET/HEAD` | `/` | Health check |
| `POST` | `/auth/register` | Cria usuário (semeia 6 categorias padrão) |
| `POST` | `/auth/jwt/login` | Login (form-encoded `username`/`password`) → `{access_token, token_type}` |
| `POST` | `/auth/jwt/logout` | Logout |
| `GET/PATCH` | `/users/me` | Perfil do usuário autenticado |
| `GET` | `/payables?month=&year=` | Lista payables do mês (do usuário) |
| `POST` | `/payables` | Cria payable |
| `PUT` | `/payables/{id}` | Atualiza payable |
| `PATCH` | `/payables/{id}/pay` | Marca como pago |
| `PATCH` | `/payables/{id}/reconcile?transaction_id=` | Concilia com transação (marca como pago) |
| `DELETE` | `/payables/{id}` | Remove payable |
| `GET` | `/payables/upcoming?days=7` | Payables PENDING vencendo nos próximos N dias |
| `GET/POST/DELETE` | `/recurring-payables` | CRUD de recorrentes |
| `GET` | `/recurring-payables/suggestions` | Sugestões de recorrentes detectadas no extrato |
| `POST` | `/recurring-payables/generate?month=&year=` | Gera payables do mês a partir dos recorrentes |
| `GET/POST/DELETE` | `/transactions` | CRUD de transações |
| `PATCH` | `/transactions/{id}` | Altera `category_id` e/ou `is_transfer` (valida que a categoria é do usuário) |
| `GET/POST` | `/categories` | Lista/cria categorias do usuário |
| `GET/POST/DELETE` | `/category-rules` | CRUD de regras de categorização |
| `GET` | `/summary?month=&year=` | Totais + by_category + budget_used_pct (income/expenses/balance mantidos por compatibilidade, não usados no dashboard) |
| `GET/POST/DELETE` | `/budgets?month=&year=` | CRUD de orçamentos |
| `GET/POST/DELETE` | `/bank-accounts` | CRUD de contas bancárias conectadas via Pluggy. No POST, `name`/`bank_name` são opcionais — omitidos, o backend deriva via `describe_item` |
| `PATCH` | `/bank-accounts/{id}` | Renomeia a conta (`name`/`bank_name`) |
| `GET` | `/bank-accounts/reconciliation-suggestions` | Sugestões pendentes de conciliação (consumidas em `/banks`) |
| `POST` | `/bank-accounts/connect-token` | Token do widget Pluggy Connect |
| `POST` | `/webhooks/pluggy` | Webhook da Pluggy (público) — dispara sync do item afetado |
| `POST` | `/bank-accounts/{id}/sync` | Sync de transações + faturas + auto-reconciliação |
| `GET` | `/credit-card-bills?month=&year=` | Lista faturas de cartão sincronizadas |
| `POST` | `/push-subscriptions` | Salva subscription VAPID |
| `GET` | `/push-subscriptions/vapid-public-key` | Chave pública para o frontend assinar push |
| `POST` | `/push-subscriptions/notify` | Dispara push de contas vencendo (do usuário autenticado) |
| `POST` | `/jobs/daily-sync` | Dispara o job de sync diário via HTTP (header `X-Cron-Secret`) |
