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

---

## 6. Rebrand: LifeOS → Lião / LIAO

Referência ao "Leão" da Receita Federal — o que tudo vê. O ícone seria um rosto
de leão desenhado, bem simples.

**Forma do nome:** os dois registros, com papéis separados. `LIAO` em caixa alta
como assinatura visual (logo, ícone, domínio, repositório) porque acento é
problema em URL, nome de pacote e caminho de arquivo — `lião.app` exigiria
punycode. `Lião` no texto corrido (interface, notificação, README), porque o til
é o que entrega o trocadilho: sem ele o nome corre o risco de ser lido como
"lí-a-o" por quem não conhece a referência.

No `manifest.json` isso cai naturalmente:

```json
"name": "Lião — Controle Financeiro",
"short_name": "LIAO"
```

`short_name` é o rótulo embaixo do ícone na tela inicial (espaço curto, caixa
alta rende melhor) e `name` é o que o iOS usa no `from ...` da notificação —
onde a pessoa lê com calma e a piada funciona.

**O que o rebrand toca:**

| Onde | O quê |
|---|---|
| `frontend/public/manifest.json` | `name`, `short_name`, `description`, `theme_color` |
| `frontend/index.html` | `<title>` e o `apple-touch-icon` (hoje inexistente) |
| `frontend/src/components/Sidebar.jsx` | o "LO" e o texto "LifeOS / Inteligência Financeira" |
| `frontend/public/` | ícones novos |
| `README.md`, `CLAUDE.md` | menções ao nome |

O título da notificação **não** entra na lista: o nome do app foi removido dele
(o iOS já exibe `from <app>`), então aquela linha acompanha o `manifest.json`
sozinha.

**Requisitos técnicos do ícone:**

- **PNG, não SVG** — 180×180 (tela inicial), 192×192 e 512×512 (manifest). O iOS
  ignora SVG, e é exatamente por isso que hoje aparece um quadrado verde com a
  inicial em vez do logo.
- **Opaco e com ~18% de margem** — o iOS não aplica fundo próprio nem arredonda
  cantos em PWA; o arquivo precisa chegar pronto.
- **Poucas formas** — juba detalhada vira borrão em 180×180.
- O `favicon.svg` atual **não é convertível por linha de comando**: tem 30
  filtros, máscaras e opacidades, e tanto ImageMagick quanto cairosvg produzem
  um raio preto sobre fundo escuro. Se a arte nova vier em SVG, que venha sem
  filtros — ou já em PNG.

**Depois de trocar o nome:** remover e re-adicionar o app na tela inicial do
iPhone. O iOS congela nome e ícone no momento da instalação e não atualiza
sozinho.
