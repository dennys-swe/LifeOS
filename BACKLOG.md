# Backlog

Pendências abertas. O que já foi entregue está no histórico do git e descrito no
`CLAUDE.md` — este arquivo guarda só o que ainda não existe.

---

## 1. Cron Job do Render nunca foi confirmado

**Impacto:** sem ele, `daily_sync` não roda sozinho. Duas coisas ficam sem gatilho:

- geração dos payables do mês a partir dos recorrentes — hoje só acontece quando
  alguém abre a tela de Contas, que chama `/recurring-payables/generate`;
- **push de contas vencendo — não tem nenhum outro gatilho.**

**Evidência de que não roda (04/08/2026):** as contas conectadas tinham
`last_sync_at` de 30/07 (Inter) contra 04/08 (Nubank, Itaú). Um job diário
sincroniza todas na mesma passada e não produziria essa defasagem — o que
mantém os dados em dia é o webhook da Pluggy, que dispara por item e só cobre
dados bancários.

**Como verificar:** dashboard do Render → o serviço `lifeos-backend` aparece
como *Web Service*; um Cron Job seria uma entrada separada na lista.

**Como resolver:** `render.yaml` já tem o Cron Job descrito (`lifeos-daily-sync`,
08:00 BRT). Ele só é aplicado se o repositório for conectado como **Blueprint** —
serviço criado à mão pelo dashboard ignora o arquivo. Alternativa sem depender
do plano do Render: qualquer agendador externo chamando
`POST /jobs/daily-sync` com o header `X-Cron-Secret`.

---

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
