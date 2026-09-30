# Fixtures da Pluggy — teste de precisão de fatura por banco

Cada pasta aqui é um **snapshot** das respostas cruas da API da Pluggy para um
cartão, mais o valor real da fatura (gabarito). `tests/test_bill_precision.py`
roda `open_bill_service.compute_open_bill_amount` contra o snapshot e compara com
o gabarito — é assim que a issue #20 (auditoria de precisão por banco) mede
progresso sem tocar em produção.

## Layout de uma pasta

```
<slug>/
  capture.yaml       # metadados: data da captura, cartão, origem, versão do SDK
  transactions.json  # lista achatada dos `results` de transactions_list (todas as páginas)
  bills.json         # lista dos `results` de bills_list (pode ser [])
  expected.yaml      # gabarito por competência
```

### `expected.yaml`

```yaml
card: "Nubank"
competencias:
  "2026-08":
    target_due_date: "2026-08-08"        # vencimento da fatura em aberto
    last_closed_due_date: "2026-07-08"   # vencimento da última fatura fechada
    fatura_real: 588.37                  # valor confirmado pelo dono
    tolerancia_pct: 0.5
    status: exato                        # exato | estimado | xfail
    # motivo: "..."                      # obrigatório quando status == xfail
```

`status: xfail` marca uma divergência **conhecida e explicada** (ex: encargos de
rotativo que o banco só calcula no fechamento). O teste espera falhar; se um dia
passar, vira `XPASS` no relatório — sinal de que o gap foi fechado e o `xfail`
pode sair.

## Onde ficam os snapshots reais

Pastas com `_synthetic` no nome são dados fabricados e **versionadas** — servem
de regressão no CI.

Capturas do banco real do dono vão em `_local/` (no `.gitignore`): têm valores e
estabelecimentos reais, e o repo é público. Gera com:

```bash
cd backend
python -m scripts.pluggy_capture <item_id> --slug nubank      # → tests/fixtures/pluggy/_local/nubank/
python -m scripts.pluggy_scrub tests/fixtures/pluggy/_local/nubank   # anonimiza no lugar
# preencher expected.yaml à mão com os valores reais de fatura
```

O teste descobre tanto as pastas versionadas quanto as de `_local/`.

## Saldo e limite (`accounts.json`)

Capturado de `accounts_list` (JSON cru, não o objeto do SDK) em 30/09/2026 contra três
itens reais: Inter (1 cartão), Itaú (2 cartões, um deles em cancelamento) e Nubank (1 conta
com 2 cartões). Os valores reais não ficam no repositório; as fixtures `_synthetic-*/accounts.json`
reproduzem os formatos. `tests/test_pluggy_account_fixtures.py` trava o que está abaixo.

| Campo | Conta | O que significa | Confirmado em |
|---|---|---|---|
| `balance` | `CREDIT` | **Limite consumido** = `creditLimit - availableCreditLimit`. Não é o valor da fatura: inclui parcelas futuras. | Inter, Itaú (2), Nubank: fecha ao centavo nos 4 cartões |
| `creditData.creditLimit` / `availableCreditLimit` | `CREDIT` | Limite total e disponível **da conta** (compartilhado entre os cartões dela). | presentes nos 4 cartões |
| `creditData.disaggregatedCreditLimits` | `CREDIT` | Uma linha por final de cartão **repetindo o mesmo limite**. Somar inflaria o limite. Vem `null` no Inter. | Itaú (2 finais), Nubank (2 finais) |
| `creditData.balanceCloseDate` | `CREDIT` | **Sempre nulo**: o dia de fechamento não vem de `accounts`. | os 4 cartões |
| `creditData.balanceDueDate` | `CREDIT` | **Não confiável para o próximo vencimento**: em 3 dos 4 cartões apontava para uma data já passada (a da última fatura fechada). | só o Inter veio no futuro |
| `balance` | `BANK` | Igual a `bankData.closingBalance`. | Inter, Itaú, Nubank |
| `bankData.overdraftContractedLimit` | `BANK` | Cheque especial contratado; **não** entra no `balance` (Itaú tinha limite contratado e saldo 0). | Itaú |
| `bankData.automaticallyInvestedBalance` | `BANK` | Saldo que rende automaticamente; no Nubank coincide com o `balance`. | Nubank |

### Consequências para as features

- **Limite consolidado (#204):** usar `creditLimit` e `availableCreditLimit` de topo, somados **por conta da Pluggy**, nunca por cartão nem por `disaggregatedCreditLimits`. Usado = `creditLimit - availableCreditLimit`, que em todos os casos coincidiu com `balance`.
- **Fechamento e vencimento (#203, #201):** não vêm de `accounts`. O vencimento vem da Bills API (`dueDate`); o fechamento precisa ser inferido (por exemplo, das transações com `billClosingDate`, ausente no Inter, ou fixado por banco). É a lacuna principal que o spike encontrou.
- **Status do cartão:** o Itaú em cancelamento veio `ACTIVE` e com linhas de limite zeradas por "conta em fase de cancelamento". Não dá para confiar só em `status` para ocultar cartão.

### Pendente de confirmação (precisa do dono)

Na data da captura, as três contas correntes tinham saldo zero ou centavos, então a semântica do `balance` de **conta corrente** só foi confirmada por coerência com `closingBalance`, não contra o app do banco com saldo relevante. Antes de o snapshot (#197) alimentar o "posso gastar?" (#201), conferir o saldo de cada conta no app do banco num dia com saldo e comparar com o `balance`.

### Como capturar de novo

`python -m scripts.pluggy_capture <item_id> --slug <banco>` agora também grava `accounts.json`. Antes de versionar, `python -m scripts.pluggy_scrub <pasta>` mascara `number`, `taxNumber`, `owner`, `transferNumber` e `identificationNumber`. **Revise o arquivo à mão:** valores monetários, nomes de titular em `name` e datas não são alterados.
