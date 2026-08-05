# Backlog

Pendências abertas. O que já foi entregue está no histórico do git e descrito no
`CLAUDE.md` — este arquivo guarda só o que ainda não existe.

---

## 1. ~~Cron Job do Render~~ — resolvido via GitHub Actions

**Confirmado em 05/08/2026:** o workspace do Render não tem Cron Job — a lista
de serviços mostra só `lifeos-backend` como Web Service (`All (1)`). Cron Job
também não entra no plano Free. Portanto `daily_sync` **nunca rodou sozinho**:
os payables recorrentes do mês só eram gerados quando alguém abria a tela de
Contas, e o push de vencimento não tinha gatilho nenhum.

**Resolvido** por `.github/workflows/daily-sync.yml`, que chama
`POST /jobs/daily-sync` com `X-Cron-Secret` às 08:00 BRT. Mesmo código que um
Render Cron Job executaria.

**Validado em produção (05/08/2026):** primeira execução real do `daily_sync`
desde que ele foi escrito — `{"processed_users":1,"synced_accounts":3,"errors":0}`,
as 3 conexões sincronizadas na mesma passada e push entregue no iPhone (a
subscription sobreviveu, então a Apple não rejeitou).

Percalço do setup, para referência: o `CRON_SECRET` do Render estava com o
placeholder do `.env.example` **duplicado** (`dev-cron-secret-change-in-prod`
colado duas vezes), o que dava 403 mesmo com o secret configurado no GitHub.
Trocado por um valor forte nos dois lados. O `.env` local segue com valor
próprio de propósito — assim um teste local nunca autentica contra produção.

`render.yaml` foi mantido como documentação da configuração equivalente, caso o
serviço migre para Blueprint num plano pago.

## 2. Categoria `Services` da Pluggy sem mapeamento

Fica sem categoria no extrato (ex: `DLKNET *AC CRATO`). Volume baixo e nome
vago demais para escolher destino sem contexto — precisa de uma decisão sobre
para onde mandar, ou de uma regra de keyword por estabelecimento.

---

## 3. Metas de poupança / objetivo

Não existe model. `Budget` (teto por categoria/mês) é outra coisa: limita gasto,
não acumula em direção a um alvo.

É o que falta para o insight de custo de oportunidade pedido pelo dono
("se não gastasse X em Y, daria para uma viagem") ser **ancorado**: sem uma meta
cadastrada, o valor de comparação teria que ser inventado pelo app — número
fabricado com aparência de conselho financeiro. Com meta, vira
*"seus R$ 884 em 12 meses no Baiaocom cobrem 44% da meta Viagem"*.

Direção considerada para o futuro: usar um modelo de linguagem para **redigir**
o insight, sempre recebendo os números já calculados pelo backend e nunca
estimando preços.

---

## 4. Tela de orçamentos

Backend completo (`/budgets`, `budget_used_pct`, insight de estouro, bloco no
dashboard), sem nenhum formulário para cadastrar. Com 0 orçamentos cadastrados,
nada disso aparece — é funcionalidade inteira parada por falta de uma tela.

---

## 5. Dívidas técnicas

- **Bundle do frontend > 500 kB** (756 kB) — o Vite avisa, não quebra.
  Code-splitting é a correção natural se crescer mais.
- **2 avisos de lint anteriores a esta leva:** `SettingsPage.jsx:148`
  (`set-state-in-effect`, reportado como erro) e `RecurringPayablesPage.jsx:61`
  (`exhaustive-deps`).
- **Suíte de frontend mínima** — só `StatusBadge`, sem cobertura de página.
- **Drill-down da fatura** ("o que compõe esta fatura") e cards de limite
  usado/disponível por cartão dependem de persistir os metadados de parcelamento
  em `transactions` (`installment_number`, `total_installments`,
  `bill_forecast_date`), hoje descartados no sync.
