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
