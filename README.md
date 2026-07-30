# LifeOS — Gestão Financeira Pessoal

> **SaaS Multi-tenant de Gestão Financeira Pessoal** focado em responder à pergunta *"Pra onde vai meu dinheiro?"*, combinando sincronização bancária real via Open Finance (Pluggy), controle de contas a pagar, conciliação inteligente e analytics com insights comparativos mês a mês.

---

## 🚀 Visão Geral

O **LifeOS** evoluiu de um gerenciador manual de checklist de contas a pagar para um ecossistema completo de inteligência financeira. Ele se conecta às suas contas bancárias reais (Itaú, Nubank, Inter e outros) através da **Pluggy API**, unificando extratos, faturas de cartão de crédito e despesas recorrentes em um dashboard visual rico, rápido e mobile-first.

---

## 🛠️ Arquitetura & Stack Tecnológica

| Camada | Tecnologia | Hospedagem / Infra |
| :--- | :--- | :--- |
| **Database** | PostgreSQL Serverless (SQLAlchemy 2.0 + Alembic) | [Neon.tech](https://neon.tech) |
| **Backend** | Python (FastAPI + Pydantic v2 + `fastapi-users` JWT) | [Render](https://render.com) |
| **Frontend** | React 19 + Vite + Tailwind CSS v4 + Recharts | [Vercel](https://vercel.com) |
| **Open Finance** | Pluggy API (OAuth / Proxy MeuPluggy) | Open Finance BR |
| **Monitoring** | Health check HEAD/GET `/` | UptimeRobot |

---

## ✨ Principais Funcionalidades

### 🏦 Open Finance & Sincronização Bancária (Pluggy)
- **Integração Real**: Conexão com instituições bancárias via conector **MeuPluggy** (permitindo uso pessoal sem custos de licença comercial).
- **Extrato & Faturas**: Sincronização automática de transações de conta corrente e faturas de cartão de crédito.
- **Janela de Payables**: Algoritmo que filtra e gera obrigações a pagar apenas para faturas no mês atual ou seguinte (`is_in_payable_window`), evitando poluição com projeções futuras distantes ou faturas antigas.

### 📊 Dashboard Inteligente & Insights
- **Herói de Gasto Mensal**: Visualização do gasto total do mês com comparativo percentual (delta) em relação ao mês anterior.
- **Faixa de Insights**: Regras automáticas (`GET /insights`) que identificam variações atípicas em categorias, maiores gastos do mês, ritmo de despesas e alertas de orçamento perto do limite ou estourado.
- **Gráficos de Tendência & Drill-Down**: Série temporal temporal via Recharts e navegabilidade por categoria (`/categoria/:id`) para inspecionar cada transação que compõe os totais.

### 🤝 Conciliação Bancária & Classificação
- **Scoring de Confiança**: Cruzamento automático entre transações do extrato e contas a pagar pendentes (score 1.0 para valor e data exatos; tolerância de valor ±5% e data ±7 dias). Auto-conciliação automática para matches únicos exatos.
- **Mapeamento de Categorias**: Conversão automática de ~61 categorias da Pluggy para as categorias do usuário, além de suporte a regras personalizadas por palavra-chave (*keywords*).
- **Tratamento de Transferências (`is_transfer`)**: Identificação automática de movimentações entre contas próprias, aportes e quitações de fatura. Elas são isoladas dos totais de gasto para evitar contagem dupla.

### 🗓️ Contas a Pagar (`Payables`) & Recorrentes
- **Gestão de Contas**: Controle de status (Pendentes, Pagas, Atrasadas) com suporte a exclusão otimista e desfaire (*undo*) via toast.
- **Templates Recorrentes**: Geração automática de obrigações mensais a partir de modelos pré-configurados sem duplicação.
- **Detecção Automática**: Sugestão automática de novos templates recorrentes com base no histórico do extrato.

### 🔐 Multi-Tenancy & Segurança
- Autenticação JWT via `fastapi-users`.
- Isolamento rigoroso de dados em nível de banco de dados (`user_id` em todas as tabelas e rotas).

### 🔔 PWA & Notificações
- PWA instalável em iOS e Android com Service Workers configurados.
- Notificações Push nativas (VAPID) para contas a vencer em breve.

---

## 📊 Modelagem de Dados

| Modelo | Descrição |
| :--- | :--- |
| `User` | Conta de usuário (`fastapi-users`): e-mail, senha criptografada e status |
| `Payable` | Conta a pagar individual (`user_id`, FKs para `recurring_payable_id` e `transaction_id`) |
| `RecurringPayable` | Template de recorrência mensal (título, valor, dia do mês) |
| `Transaction` | Transação de extrato bancário ou importada (`is_transfer`, `external_category`) |
| `CreditCardBill` | Fatura de cartão de crédito sincronizada via Pluggy Bills API |
| `Category` | Categoria com cor personalizada (`color_hex`) por usuário |
| `CategoryRule` | Regra de categorização por palavra-chave e prioridade |
| `Budget` | Orçamento mensal por categoria (`month`, `year`, `amount`) |
| `BankAccount` | Conta/Conexão bancária conectada via Pluggy |
| `PushSubscription` | Inscrição VAPID para envio de push notifications no dispositivo |

---

## ⚡ Destaques de Engenharia

- **Timezone Safety**: Datas trafegam e são manipuladas estritamente como strings `YYYY-MM-DD` (evitando bugs de deslocamento por fuso horário/GMT offset).
- **Isolamento de Transferências**: Transações marcadas como `is_transfer` são filtradas nos cálculos do dashboard e orçamentos, prevenindo que o pagamento de fatura duplique os gastos já contabilizados no cartão.
- **High Availability & Warmup**: Rota raiz responde a requisições `HEAD` mantendo o container no Render ativo via UptimeRobot e eliminando *cold starts*.
- **Suíte de Testes Leve**: Testes automatizados executam usando SQLite em memória via Pytest, sem necessidade de dependência de banco externo.

---

## 🚀 Como Rodar Localmente

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend

```bash
cd backend
cp .env.example .env          # Configurar DATABASE_URL, SECRET_KEY, PLUGGY credentials, etc.
pip install -r requirements.txt
alembic upgrade head          # Aplicar migrations
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev                   # Servidor de desenvolvimento rodando em http://localhost:5173
```

### Testes

```bash
cd backend && pytest          # Executa 200+ testes unitários/integração em SQLite
cd frontend && npm test       # Executa testes unitários do frontend
```

---

## 📚 Documentação Complementar

- **[CLAUDE.md](file:///home/dennysdev/Projetos/Pessoal/LifeOS/CLAUDE.md)**: Guia completo de arquitetura, padrões de código, instruções para IA, rotinas de deploy e regras de negócio detalhadas.
- **[plano_lifeos.md](file:///home/dennysdev/Projetos/Pessoal/LifeOS/plano_lifeos.md)**: Registro histórico das últimas alterações entregues em produção, lições operacionais e backlog futuro.

---

*Desenvolvido por Dennys Alves — Última atualização: julho de 2026*

