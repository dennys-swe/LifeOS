# Roadmap: controle financeiro "na palma da mão"

> Proposta de 30/09/2026. Complementa o Epic #166 (tese de saúde financeira) — **não o substitui**.
> Onde já existe issue, o item só aponta para ela. O que é novo está marcado **[NOVO]**.

## 1. Objetivo e critério de sucesso

O produto é "vital" quando o usuário para de abrir o app do banco. Isso exige duas coisas, nesta ordem:

1. **Confiança:** os números batem com a realidade e o app avisa quando não batem.
2. **Uma resposta clara para "posso gastar isso agora?"** olhando para frente, não só para trás.

IA é a camada de cima (entender, explicar, conversar). Ela nunca é a fonte de um número.

**Perfil de uso prioritário: tudo no cartão de crédito.** O dono concentra os gastos no cartão. Nesse perfil o dinheiro só sai da conta quando a **fatura é paga**, então a pergunta real não é "quanto tenho na conta?", e sim **"quanto posso gastar no cartão até o fechamento e ainda pagar a fatura inteira, sem rotativo?"**. O plano (B2, B5, C1) é desenhado em torno disso. A visão por conta corrente continua existindo, mas é secundária. O perfil também torna o rotativo o risco financeiro mais caro de evitar: o histórico do dono tem "Saldo em atraso" de R$ 456,02 em set/2026.

**Métricas** (medidas no uso do próprio dono, antes de qualquer usuário externo):

| Métrica | Alvo inicial |
|---|---|
| Despesas sem categoria no mês | < 3% (mede a #169) |
| Divergência de saldo não explicada (A3) | 0 contas por mais de 1 sync |
| Erros de classificação achados na auditoria manual | tendência a 0 por mês |
| Aberturas do app do banco para "ver saldo" | cair (autorrelato semanal) |
| Custo de IA por usuário/mês | teto configurável, valor a definir (decisão 3, seção 9) |

## 2. Princípios

1. **Determinístico primeiro, IA no que sobra.** Cálculo é SQL/Python testado; IA só redige ou classifica padrões.
2. **Sem categoria é melhor que categoria errada** (princípio já adotado; vale para IA também).
3. **A IA nunca aplica nada sozinha.** Sugere com prévia ("isso altera N lançamentos") e o usuário confirma.
4. **Nunca sobrescrever dado original.** Descrição, valor e categoria da Pluggy ficam intactos; o enriquecimento vive em campos próprios.
5. **Multi-tenant sempre:** todo service recebe `user_id` e filtra por ele. Toda tabela nova tem `user_id` (FK, CASCADE).
6. **Privacidade por padrão (LGPD):** repo público, produto multiusuário. Ver seção 6.
7. **Sinalizar incerteza.** Fatura de baixa confiança, saldo divergente e dado desatualizado aparecem na tela, não escondidos.

## 3. Mapa: o que já existe e o que falta

| Capacidade | Estado |
|---|---|
| Sync Pluggy, dedup, conciliação de payables | existe |
| Fatura de cartão em aberto reconstruída + `is_low_confidence` | existe (#147); **UI não exibe** |
| Contas a pagar, recorrentes, detecção de recorrência (18 meses) | existe |
| Insights comparativos do mês, server-side (`insight_service`) | existe; #153 e #154 evoluem |
| Push de vencimento (VAPID) + cron diário via GitHub Actions | existe |
| Orçamento por categoria (backend completo) | existe; **sem tela** (BACKLOG #4) |
| Sinais de classificação, `classification_source`, campos estruturados | existe (#167) |
| Renda correta (eco de fatura e transferência própria fora da renda) | existe (#172) |
| Índice de comprometimento de renda | #150 aberta |
| Projeção de fluxo de caixa 30/60 dias | #151 aberta |
| Orçamento dinâmico (ritmo diário permitido) | #152 aberta |
| Insights com ação sugerida / thresholds proporcionais | #153, #154 abertas |
| Contraparte (transferência entre pessoas) | #168 aberta |
| Medir resíduo sem classificação | #169 aberta |
| IA de último recurso / IA auditora-sombra | #170, #171 abertas |
| Frontend da fase 2, notificações multi-canal | #155–#165 abertas |
| **Saldo bancário persistido** | **não existe [NOVO]** |
| **Conciliação de saldo e checagem de invariantes** | **não existe [NOVO]** |
| **Enriquecimento de todas as transações (nome limpo)** | **não existe [NOVO]** |
| **Motor de alertas com deduplicação e preferências** | **não existe [NOVO]** |
| **Metas** (BACKLOG #3) | não existe |
| **Perguntas em linguagem natural** | não existe [NOVO] |

## 4. Ordem e dependências

```
A. Confiança nos dados ──► B. Olhar para frente ──► C. Empurrar (alertas)
   (A1→A2→A3, A4→A5)          (B0→B1→B2→B3→B4)         (C1→C2, usa #161)
        │                          │
        └──────────► D. Infra de IA + enriquecimento ──► E. Insights narrados e conversa
                        (D0→D1→D2, D3)                     (E1, E2, E3)
```

Regra de ouro: **A antes de tudo.** Um insight bonito em cima de dado errado parece confiável e engana. Hoje mesmo o Ohio tinha R$ 2,2 mil de eco de fatura contado como renda.

Ritmo de trabalho (regra do projeto): **uma issue por vez, uma branch/PR por issue**, `Closes #N` em inglês.

## 5. Épicos e itens

Cada item traz: escopo, design, testes, aceite, dependência e **modelo sugerido** (Opus = arquitetura/revisão, Sonnet = lógica de negócio, Haiku = mecânico).

### A. Confiança nos dados

**Correção importante sobre conciliação.** Bater o saldo detecta **transação faltando ou duplicada**, porque o saldo real é a soma de todas as movimentações, incluindo transferências. Ele **não** detecta classificação errada (uma transferência marcada como renda não muda o saldo). Por isso A3 e A4 são checagens diferentes e ambas necessárias.

**A1 — Spike: saldo e limite por tipo de conta [NOVO]**
- Capturar `accounts` de cada banco (`scripts.pluggy_capture`), mascarar (`scripts.pluggy_scrub`), versionar fixtures sintéticas. Documentar em `tests/fixtures/pluggy/README.md` o que `balance` significa por tipo e banco.
- Já sabemos: em cartão, `balance` é limite consumido e a semântica varia por banco (`open_bill_service`). Para conta corrente, **confirmar** antes de assumir que é saldo disponível.
- Para cartão, confirmar também **limite total, limite disponível, dia de fechamento e dia de vencimento** por banco (campos de `creditData`). São a base do B2 e do B5.
- Aceite: tabela "banco × tipo × significado do balance" documentada com dado real.
- Modelo: Sonnet (captura e análise); Haiku para o scrub.

**A2 — Persistir saldo (snapshots) [NOVO]**
- Tabela `account_balance_snapshots` (`id`, `user_id`, `bank_account_id`, `pluggy_account_id`, `balance`, `currency`, `captured_at`, `source`). Índice `(bank_account_id, captured_at)`.
- O sync grava um snapshot por conta de tipo BANK por execução. Retenção: 1 por dia depois de 90 dias.
- Migration escrita à mão e validada contra o Postgres do docker-compose (não só SQLite).
- Testes: grava snapshot; idempotência por sync; isolamento entre usuários; conta de cartão não gera snapshot de saldo.
- Modelo: Haiku (model/schema/migration), Sonnet (hook no sync).

**A3 — Conciliação de ingestão [NOVO]**
- Função pura: para cada par de snapshots consecutivos, `Δsaldo` deve ser igual a `Σ(transações da conta entre as duas capturas, todas, incluindo transferências)`. Diferença acima da tolerância = transação faltando ou duplicada naquela janela.
- Saída: `IngestionGap(conta, janela, diferença, hipótese)`, onde a hipótese distingue "faltando" (diferença = valor de uma transação plausível) de "duplicada".
- Atenção: transações pendentes e datas de lançamento vs. efetivação podem gerar falso positivo. Tolerância configurável e janela mínima de 24h.
- Testes: caso limpo, faltante, duplicada, pendente que vira efetivada, virada de mês, fuso.
- Aceite: divergência aparece por conta com a janela e o valor, e some quando o dado é corrigido.
- Modelo: Opus revisa o desenho (dado financeiro, muitos falsos positivos possíveis); Sonnet implementa.

**A4 — Invariantes de classificação [NOVO] + #169**
- Regras determinísticas que sinalizam suspeita, sem alterar nada:
  1. **Espelho não marcado:** entrada e saída de mesmo valor em até 2 dias entre contas do mesmo usuário, sem `is_transfer`.
  2. **Eco de fatura:** entrada `^PAGAMENTO` sem `is_transfer`.
  3. **Entrada grande atípica** (acima de X vezes a mediana de renda) sem categoria de renda conhecida.
  4. **Sem categoria** e **`Investments` com regra ampla** casando com descrição de compra.
  5. **Pares de crédito/estorno** (ex: `Crédito de atraso` ↔ `Saldo em atraso`) sem vínculo.
- Substitui os `_audit*.py` por um comando versionado `python -m scripts.audit_classification` (somente leitura, dry-run por padrão, `--user`), com testes.
- Grava `data_quality_issues` (`user_id`, `kind`, `transaction_ids`, `severity`, `status`, `detected_at`) para a UI e para a #171.
- **#169** entra aqui: o relatório de resíduo (% sem categoria, sem `intent_type`, etc.) sai do mesmo comando.
- Testes: um por invariante, com os casos reais de 30/09 como fixtures sintéticas (MERCADOLIVRE como `Investments`, `PAGAMENTO ON LINE` como renda).
- Modelo: Sonnet; Opus revisa a lista de invariantes.

**A5 — UI "Saúde dos dados" e correção em um toque [NOVO]**
- Banner no dashboard com contagem de problemas; tela de lista com prévia por item; ação "corrigir" abre a prévia ("isso altera N lançamentos") e só aplica com confirmação.
- A correção manual grava `classification_source='manual_override'` (já protegido do sync) e pode virar **sugestão de regra**, nunca regra automática.
- Aproveita para exibir o `is_low_confidence` da fatura (#147), hoje sem UI.
- Testes de frontend: lista, prévia, confirmação, estado vazio, erro de rede.
- Modelo: Haiku para UI simples; Sonnet para o endpoint de aplicação com prévia.

### B. Olhar para frente

**B0 — Definição de renda (conversa antes de codar) [pré-requisito de #150]**
- Perguntas em aberto: janela de média, tratamento de renda variável (Uber semanal), se "Renda extra" via regra entra, tratamento de Larissa (transferência, não renda).
- Entregável: uma página curta em `docs/` com a definição e exemplos. Sem código.

**B1 — Serviço de compromissos (linha do tempo) [dentro da #151]**
- `commitments_service.get_timeline(user_id, horizon_days)` retorna itens datados: payables pendentes, faturas (aberta + futuras), recorrentes ainda não geradas, parcelas em conta.
- **Fatura aberta já gera `Payable`** (`CreditCardBill` com `status=OPEN` tem payable PENDING atualizado a cada sync). Para a fatura **atual**, a fonte é o payable; somar payable e fatura aberta conta a mesma fatura duas vezes. Faturas futuras sem payable (fora da janela de criação) vêm do `CreditCardBill`/projeção.
- **Risco principal: dupla contagem.** Parcela futura de cartão já está dentro da fatura futura (Itaú emite parcelas futuras como transações; Nubank só a do ciclo). Regra: para cartão, o compromisso é a **fatura**, nunca a parcela solta. `open_bill_service` já trata esse conflito; reutilizar.
- Testes: um caso por banco com as fixtures existentes; parcela que aparece nas duas fontes conta uma vez; fatura de baixa confiança marcada como estimativa.
- Modelo: Opus revisa (dinheiro, dupla contagem); Sonnet implementa.

**B2 — "Posso gastar?" centrado no cartão [NOVO, sobre #151 e #152]**
- Para o perfil cartão (prioritário): `folga_no_ciclo = saldo projetado no vencimento da fatura − fatura projetada no vencimento`.
  - **Saldo projetado** = saldo das contas correntes hoje (A2) + entradas conservadoras até o vencimento (B3) − outros compromissos até lá (payables, recorrentes).
  - **Fatura projetada** = fatura aberta atual (`open_bill_service`) + parcelas já comprometidas que caem nesse ciclo (B1) + gasto esperado até o fechamento pelo ritmo do usuário.
  - Resposta ao usuário: *"Você ainda pode gastar R$ X no cartão até o fechamento (dia D) e pagar a fatura sem usar o rotativo."* Negativo vira alerta (C1), não só número vermelho.
- Para conta corrente: `livre = Σ saldo das contas correntes (A2) − compromissos até a próxima entrada esperada (B1)`. Investimento e conta de cartão ficam fora.
- Endpoint `GET /planning/safe-to-spend` retorna `folga_no_ciclo`, `livre_conta`, `fechamento`, `vencimento`, `itens` e `confianca`. A confiança é rebaixada se houver divergência A3, fatura estimada (`is_low_confidence`) ou snapshot velho.
- **Nunca** mostrar um número sem indicar a confiança. Snapshot com mais de 24h vira "dado de ontem".
- Testes: folga positiva, negativa, fatura de baixa confiança, vencimento antes do fechamento seguinte, vários cartões (Itaú junta cartões numa `accountId`, separar por `card_label`), snapshot velho, divergência ativa, isolamento de usuário.
- Aceite: com os dados do dono, o número bate à mão com (saldo dos bancos − faturas − contas do período).

**B3 — Renda irregular [NOVO, sobre #150]**
- Baseline **conservador**: mediana das últimas N semanas de renda (excluindo transferências e apostas), mais P25 como cenário ruim. "Colchão" em dias = livre ÷ gasto diário mediano.
- Não prever a próxima entrada: só mostrar "se nada entrar, dura X dias".
- Testes: semanas vazias, outlier, poucas semanas de histórico (mostrar "dados insuficientes").
- Depende de B0. Modelo: Sonnet.

**B5 — Visão por ciclo de fatura [NOVO]**
- Para quem gasta no cartão, o mês-calendário engana: o que importa é o **ciclo** (do fechamento anterior ao próximo).
- Mostrar: gasto do ciclo atual vs. ciclos anteriores no mesmo ponto do ciclo, dias até o fechamento, ritmo diário permitido (#152 adaptado ao ciclo) e **fatura futura já comprometida por parcelas** (`installment_number/total` já persistidos no #167).
- Orçamento por categoria passa a poder ser **por ciclo** (decisão 7, seção 9).
- Cuidado: parcelas futuras dentro da fatura futura não podem ser contadas de novo (mesma regra de dupla contagem do B1). Itaú emite as parcelas futuras; Nubank só a do ciclo corrente.
- Testes: virada de ciclo, compra no dia do fechamento, parcela que cruza ciclos, cartão sem `cardNumber` (Inter), dois cartões no mesmo item.
- Depende de A1 (datas de fechamento e vencimento) e B1. Modelo: Sonnet; Opus revisa.

**B4 — UI do Home [#155–#160, #158, #189]**
- Uma tela: **livre agora**, o que vence nos próximos 7 dias, um alerta. Linha do tempo de 30/60 dias abaixo. Mobile primeiro.
- Modelo: Haiku para componentes; Sonnet para o contexto de dados.

### C. Empurrar

**C1 — Alertas [sobre #161, #162, #164, #165]**
- Já existem as issues de infraestrutura multi-canal com preferência e log de deduplicação (#161), orçamento estourando (#162), recorrência que sumiu (#164) e gasto atípico (#165). **Não duplicar:** este item só acrescenta as regras novas abaixo (em especial o risco de rotativo) e o limite diário, reaproveitando o que a #161 entregar.
- Regras puras: **fatura projetada maior que o saldo disponível no vencimento (risco de rotativo)**; fatura fecha em N dias; assinatura nova ou reajustada (reusa `recurring_detection`); cobrança duplicada; gasto atípico por categoria (mediana e MAD, não média); saldo livre projetado negativo; divergência de dados (A3).
- Tabelas: `alert_events` (`user_id`, `kind`, `dedup_key`, `payload`, `created_at`, `sent_at`, `dismissed_at`) e preferências por usuário. **Cooldown e deduplicação** por `dedup_key`.
- Gancho no `daily_sync` (já roda 08:00 BRT via GitHub Actions). Canal inicial: push existente; #161 abre e-mail/Telegram.
- Limite duro: no máximo 1 alerta por dia por padrão. Alerta demais vira ruído e o usuário desliga.
- Testes: dedup, cooldown, preferências, limite diário, falha de canal não derruba o job.
- Modelo: Sonnet.

**C2 — Resumo periódico [#163]**
- Números calculados no backend; texto por template. Entra na versão com IA (E1) depois.

### D. IA: infraestrutura e enriquecimento

**D0 — Infraestrutura de IA [NOVO]**
- `app/services/ai/client.py` sobre o SDK da Anthropic; modelos por papel (barato para classificar, melhor para redigir). Ver a skill `claude-api` para ids e parâmetros vigentes.
- Feature flag, **teto de custo** por usuário/mês e kill switch em `settings`.
- Tabela `ai_calls` (`user_id`, `purpose`, `model`, `tokens_in/out`, `cost`, `status`, `created_at`) **sem conteúdo do prompt**.
- Redator de PII antes de qualquer envio (nomes de pessoas, CPF/CNPJ de pessoa física, e-mail, telefone). Ver seção 6.
- Roda assíncrono, fora do caminho do sync. Falha de IA nunca falha o sync.
- Testes com cliente falso: timeout, resposta inválida, teto estourado, flag desligada, PII removida do payload.
- Modelo: Opus desenha; Sonnet implementa.

**D1 — Enriquecimento determinístico [NOVO]**
- Campos novos em `transactions`: `display_name`, `canonical_merchant` (nullable). A `description` original **não muda**.
- Limpeza por regra: sufixos de cidade (`CRATO BRA`, `OSASCO`), prefixos (`MP `, `PIX `), parcela `1/3` (já em `installment_number`), colagem de palavras.
- Cobre a maior parte sem IA. Medir com a #169 o que sobra.
- Testes: tabela de descrições reais mascaradas → nome esperado; idempotência; não quebra o dedup (`_same_purchase_description` usa a descrição original).
- Modelo: Sonnet; Haiku para a tabela de testes.

**D2 — Enriquecimento por IA [#170 estendida]**
- Só para **padrões** de descrição distintos que a D1 não resolveu, nunca transação a transação.
- Cache por `(descrição_normalizada, direção, tipo_de_conta, categoria_pluggy)`. `canonical_merchant` pode ser global, e só para **estabelecimento**. `intent_type` é sempre por usuário.
- Cada entrada guarda `source`, `model_version`, `confidence`, `created_at`, e é invalidável. Baixa confiança = sem classificação.
- Precedência (já decidida): override manual > regra do usuário > campos estruturados Pluggy > regras do sistema > cache do usuário > cache global > IA.
- Só entra se a #169 mostrar que o resíduo justifica.

**D3 — IA auditora-sombra [#171]**
- Job semanal: classifica os padrões distintos do usuário **sem ver** a decisão da regra; divergência vai para `data_quality_issues` (A4). **Nunca aplica.**
- Reaproveita D0 e a fila do A5.

### E. IA: insights e conversa

**E1 — Insights narrados [sobre #153]**
- O `insight_service` já monta texto no servidor. Passa a produzir **fatos estruturados** (números já calculados), e a IA só redige.
- **Validação numérica:** todo número no texto gerado precisa existir nos fatos. Se não bater, cai no texto de template. Sem exceção.
- Testes: texto com número inventado é rejeitado; fallback funciona; IA desligada = comportamento atual.

**E2 — Metas [BACKLOG #3]**
- Model `Goal` (nome, alvo, prazo, aporte). Ancora o insight de custo de oportunidade ("seus R$ 884 em 12 meses cobrem 44% da meta Viagem"). Sem meta cadastrada, o app **não** inventa valor de comparação.

**E3 — Perguntas em linguagem natural [NOVO]**
- A IA chama **ferramentas com parâmetros fechados** (`spend_by_category(period)`, `compare_periods`, `list_transactions(filter)`, `get_commitments`). SQL livre nunca.
- **O `user_id` é injetado pelo servidor**, nunca pelo modelo. Rate limit. Resposta cita o período e a fonte dos números.
- Pergunta sobre transferência entre pessoas responde com totais, sem enviar nomes ao provedor.
- Testes: tentativa de injeção de `user_id` na chamada de ferramenta, prompt injection vindo da descrição de uma transação, parâmetro inválido, teto de custo.
- Só depois de A, B e D0. Modelo: Opus desenha, Sonnet implementa.

### F. Dívidas que destravam

- Tela de orçamentos (BACKLOG #4): backend pronto, sem formulário. Habilita #152.
- UI do `is_low_confidence` (#147), incluída no A5.
- Reconhecimento automático de créditos-espelho no `is_transfer` (`Crédito de atraso`, `Encerramento de dívida`, `Juros de dívida encerrada`, `Crédito de parcelamento de compra`). Hoje só o script corrigiu o histórico; transação nova do mesmo tipo volta a contar errado.
- Drift do `alembic check` e blindagem de migrations no deploy.

## 6. Regras de IA e privacidade (duras)

1. **Transferência entre pessoas e qualquer nome de pessoa nunca vai para o provedor de IA.** Vale para enriquecimento, auditoria e conversa.
2. **Opt-in explícito** por usuário para recursos de IA, com texto claro do que sai do sistema.
3. Só saem do sistema: nome de estabelecimento limpo, categoria, direção, faixa de valor e agregados. Nunca CPF, e-mail, telefone ou número de conta.
4. Cache global só para `canonical_merchant` de estabelecimento. `intent_type` e qualquer coisa que dependa do perfil do usuário é por usuário.
5. Correção do usuário nunca alimenta cache global.
6. Descrição de transação é **entrada não confiável** (prompt injection): vai em campo delimitado, nunca como instrução.
7. Sem conteúdo de prompt em log nem em `ai_calls`.
8. Falha de IA degrada para o comportamento sem IA, nunca para erro.

## 7. Estratégia de testes

- **Cada item entrega testes junto**, e a suíte continua compatível com SQLite (`summary_service` agrega em Python; nada de `date_trunc`).
- **Migrations** validadas com `alembic upgrade head` no Postgres do docker-compose (a suíte usa SQLite e não pega drift de índice).
- **Fixtures** sintéticas versionadas; capturas reais só em `_local/` (repo público).
- **Casos reais viram regressão:** os erros de 30/09 (MERCADOLIVRE como `Investments`, `PAGAMENTO ON LINE` como renda, pares de atraso) entram como testes sintéticos em A4.
- **Multi-tenant:** todo service novo tem teste com dois usuários provando isolamento.
- **IA:** sempre com cliente falso; nenhum teste chama a API real.
- `ruff check` **e** `ruff format` antes do push. Frontend: `npm run lint` e `npm test`.

## 8. Processo

- Uma issue por vez, uma branch/PR por issue.
- `/code-review` só onde há risco (dado financeiro, migration, concorrência, segurança), no máximo 2 rodadas. UI e mudança mecânica: teste + CI.
- **Sem fan-out de agentes.** A coluna "modelo sugerido" indica o nível de esforço por item, executado em sequência.
- Antes de qualquer script contra produção: confirmar o host com o `DATABASE_URL` do Render. **Produção = Ohio (`us-east-2`)**.
- Deploy primeiro, limpeza de dado depois (o próximo webhook re-executa o código deployado).
- Atualizar `CLAUDE.md` e `docs/` em cada PR que mudar comportamento.

## 9. Decisões em aberto (precisam do dono)

1. **Definição de renda** (B0): janela de média, renda variável, papel da "Renda extra".
2. **Saldo livre:** contas de investimento entram? Reserva de emergência é separada? (Para o perfil cartão, recomendo que não entrem.)
3. **Teto de custo de IA** por usuário/mês e provedor/modelo por papel.
4. **Canal do resumo semanal:** push apenas, ou e-mail/Telegram junto com a #161? WhatsApp fica de fora por custo e API oficial.
5. **Consentimento de IA:** texto e local do opt-in.
6. **Orçamento por mês-calendário ou por ciclo de fatura?** Para o perfil cartão, recomendo o ciclo.
7. **Quando abrir para outros usuários:** define quanto do A5 e da privacidade precisa estar pronto antes.

## 10. Fora de escopo por enquanto

- IA lendo transações cruas para calcular totais.
- Aplicação automática de regra ou categoria pela IA.
- Previsão de renda futura (só cenário conservador).
- WhatsApp como canal.
- Recomendação de investimento.
