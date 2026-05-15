# LifeOS - Gestão Financeira Pessoal

SPA fullstack responsivo para controle de contas a pagar, transações, orçamento por categoria e conciliação bancária. Foco em integridade de dados e experiência mobile-first.

---

## Arquitetura (Cloud Native)

| Camada | Tecnologia | Hospedagem |
| :--- | :--- | :--- |
| Database | PostgreSQL Serverless | Neon.tech |
| Backend | FastAPI (Python) | Render |
| Frontend | React + Vite + Tailwind CSS v4 | Vercel |
| Monitoring | Health check HEAD/GET `/` | UptimeRobot |

---

## Funcionalidades

### Contas a Pagar (Payables)
- CRUD completo com persistência no PostgreSQL
- Filtros por status: Pendentes, Pagas, Atrasadas
- Exclusão com **Undo** via toast (remoção otimista + `setTimeout` de 5s)
- Badge na navbar com contagem de contas vencendo em ≤7 dias

### Recorrentes
- Templates de recorrência (título, valor, dia do mês)
- Geração automática para o mês sem duplicatas

### Categorias e Orçamento
- CRUD de categorias com cor personalizada
- Regras de categorização por keyword (prioridade configurável)
- Orçamento mensal por categoria com `% utilizado`

### Importação e Conciliação
- Upload de extrato CSV com mapeamento dinâmico de colunas
- Sugestões automáticas de conciliação com scoring de confiança (valor ±5%, data ±7 dias)

### Dashboard
- Cards de saldo (receita, despesa, saldo líquido)
- Barras de progresso de orçamento por categoria
- Gráfico de histórico dos últimos 6 meses

### PWA e Push Notifications
- Manifest e service worker configurados (instalável no iOS/Android)
- Push notifications VAPID para contas vencendo em breve

---

## Destaques de Engenharia

- **Timezone Fix:** datas trafegam e são comparadas como strings `YYYY-MM-DD` (nunca `new Date(due_date)`), eliminando o deslocamento de dia por offset GMT.
- **High Availability:** rota raiz usa `@app.api_route` para suportar método `HEAD`, mantendo a instância do Render ativa via UptimeRobot e reduzindo cold start de ~20s para <2s.
- **Compatibilidade SQLite/PostgreSQL:** agregações do `summary_service` feitas em Python (não `GROUP BY` SQL) para que os testes rodem em SQLite em memória sem mock de banco.

---

## Modelagem de Dados

| Modelo | Descrição |
| :--- | :--- |
| `Payable` | Conta a pagar. FKs nullable: `recurring_payable_id`, `transaction_id` |
| `RecurringPayable` | Template de recorrência (title, amount, day_of_month, active) |
| `Transaction` | Transação de extrato bancário |
| `Category` | Categoria com cor (`color_hex`) |
| `CategoryRule` | Regra de categorização por keyword (UPPERCASE, priority DESC) |
| `Budget` | Orçamento mensal por categoria — unique(category_id, month, year) |
| `BankAccount` | Conta bancária (sync retorna 501) |
| `PushSubscription` | Subscription VAPID para push notifications |

---

## Como rodar localmente

### Backend

```bash
cd backend
cp .env.example .env   # preencher DATABASE_URL
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev            # VITE_API_URL padrão: http://localhost:8000
```

### Testes

```bash
cd backend && pytest   # SQLite em memória, sem banco externo
```

---

*Desenvolvido por Dennys Alves — Última atualização: maio de 2026*
