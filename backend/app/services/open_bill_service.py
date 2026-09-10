"""Reconstrói a fatura do ciclo **em aberto** a partir das transações da Pluggy.

Motivação: a Bills API só publica a fatura depois que o banco fecha o ciclo, e o
atraso varia muito por instituição — Nubank e Itaú só expuseram a fatura entre 0
e 7 dias antes do vencimento, enquanto o Inter já projeta faturas com quase um
ano de antecedência. Entre o fechamento real e a publicação, o dashboard ficava
sem nenhuma informação da fatura corrente.

`account.balance` **não** serve como substituto: é o limite consumido, e a
semântica varia por banco. No Nubank ele soma o ciclo seguinte e as parcelas
ainda não cobradas (R$ 787,16 contra R$ 588,37 de fatura real); na Luiza ele
coincide com a fatura. Usá-lo direto mostraria valores inflados sem aviso.

Os bancos publicam parcelamento de duas formas incompatíveis, e o cálculo
precisa das duas:

- **Nubank** só emite a parcela do ciclo corrente; as futuras não existem como
  transação e precisam ser projetadas.
- **Itaú/Luiza** já emitem todas as parcelas futuras como transações pendentes
  datadas no vencimento em que serão cobradas — projetar aqui contaria em
  dobro, e a mesma parcela ainda reaparece depois de já ter sido faturada.

Validado contra os valores reais informados pelo dono (2026-08-04): Nubank
R$ 588,37 exato. O Itaú Click fica acima porque está em refinanciamento e os
encargos de rotativo só são calculados pelo banco no fechamento — nenhuma soma
de transações antecipa esse valor.
"""

from __future__ import annotations

import re
from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

# Categoria da Pluggy para quitação de fatura. O pagamento de uma fatura fica
# registrado como transação da fatura **seguinte** — somá-lo zeraria o ciclo
# novo em vez de abater o anterior.
PAYMENT_CATEGORY_ID = "05100000"

# Ancorado no início: "PAGAMENTO COM SALDO" / "Pagamento recebido" são quitação;
# "JUROS PAGAMENTO CONTAS" é encargo e não pode ser excluído.
# Nem todo pagamento cai na categoria certa: "PAGAMENTO COM SALDO" (Itaú/Luiza)
# vem como `Transfers`, mesma categoria de créditos legítimos que abatem a
# fatura ("Encerramento de dívida"). A descrição é o que separa os dois.
_PAYMENT_DESCRIPTION = re.compile(r"^\s*PAGAMENTO\b", re.IGNORECASE)

# "MERCADINHO SAO LUIZ02/02" / "Expresso Guanabara 1/5" — o número da parcela
# entra na descrição, então precisa sair para agrupar a mesma compra.
_INSTALLMENT_SUFFIX = re.compile(r"\s*\d{1,2}\s*/\s*\d{1,2}\s*$")


def _amount(tx: dict) -> Decimal:
    """Valor em BRL. Compras em moeda estrangeira trazem o convertido à parte."""
    converted = tx.get("amountInAccountCurrency")
    raw = converted if converted is not None else tx.get("amount")
    return Decimal(str(raw or 0))


def _metadata(tx: dict) -> dict:
    return tx.get("creditCardMetadata") or {}


def _is_payment(tx: dict) -> bool:
    if tx.get("categoryId") == PAYMENT_CATEGORY_ID:
        return True
    return bool(_PAYMENT_DESCRIPTION.search(tx.get("description") or ""))


def _month_key(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def _add_months(year: int, month: int, offset: int) -> tuple[int, int]:
    index = month + offset
    return year + (index - 1) // 12, (index - 1) % 12 + 1


def _months_between(start: str, end: str) -> int:
    sy, sm = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    return (ey - sy) * 12 + (em - sm)


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _installment_parts(tx: dict) -> tuple[Optional[int], Optional[int]]:
    meta = _metadata(tx)
    return meta.get("installmentNumber"), meta.get("totalInstallments")


def _purchase_key(tx: dict) -> tuple:
    """Identifica a compra por trás de um parcelamento.

    Não dá para usar `purchaseDate`: a mesma parcela reemitida vem com timestamp
    deslocado (`2026-04-30T15:00:01` virou `2026-05-01T00:42:23`), o que quebra
    o agrupamento justamente nos casos de duplicata que ele precisa detectar.
    """
    meta = _metadata(tx)
    description = _INSTALLMENT_SUFFIX.sub("", (tx.get("description") or "").strip().upper())
    return (meta.get("cardNumber"), meta.get("totalInstallments"), description)


def _bill_month(tx: dict, last_closed_due_date: Optional[date], target_key: str) -> Optional[str]:
    """Em qual competência esta transação vai ser cobrada?

    `billForecastDate` é a resposta direta quando existe. Sem ela, a data cai em
    duas leituras: pendência entre o fechamento e o vencimento da última fatura
    pertence ao ciclo seguinte (Nubank), e parcela futura vem datada no próprio
    vencimento em que será cobrada (Itaú/Luiza). A janela cobre as duas.
    """
    meta = _metadata(tx)
    forecast = meta.get("billForecastDate")
    settled = bool(meta.get("billId")) or tx.get("status") != "PENDING"
    tx_date = _parse_date(tx.get("date"))

    # Rótulo adiantado do Itaú: uma pendência **não faturada** comprada DENTRO do
    # mês-alvo mas com `billForecastDate` apontando o mês seguinte (compras de
    # 05–07/09 vinham como "2026-10"). A data da compra manda. Não confundir com
    # uma compra de mês anterior que aponta um ciclo futuro — essa é legítima e
    # o `_month_key(tx_date) == target_key` a exclui.
    if (
        not settled
        and forecast
        and tx_date is not None
        and forecast > target_key
        and _month_key(tx_date) == target_key
    ):
        return target_key

    # Lançamento já faturado: a competência dele (a do billId) é definitiva.
    # `forecast` pode ser None aqui — devolver None mantém o comportamento
    # anterior (excluído da reconstrução do ciclo aberto).
    if settled:
        return forecast

    if forecast and forecast >= target_key:
        return forecast
    if last_closed_due_date is None:
        return None

    # Chegou aqui: pendência não faturada. Ou não declara competência, ou
    # declara uma que já fechou — o Itaú rotula pelo mês da compra, então
    # lançamentos de 15 a 25/07 vinham como "2026-07" com a fatura de julho já
    # paga. Em ambos os casos a cobrança rolou para o ciclo seguinte.
    if tx_date is None:
        return None
    if forecast and forecast < target_key:
        return target_key
    if tx_date < last_closed_due_date.replace(day=1):
        return None
    # Antes do vencimento da última fatura o ciclo seguinte já está acumulando;
    # a partir dele, a data do lançamento já aponta a própria competência (é
    # assim que Itaú e Luiza emitem parcela futura).
    if tx_date < last_closed_due_date:
        return target_key
    return _month_key(tx_date)


def compute_open_bill_amount(
    transactions: Iterable[dict],
    target_due_date: date,
    last_closed_due_date: Optional[date],
) -> Decimal:
    """Soma o que deve cair na fatura que vence em `target_due_date`."""
    return explain_open_bill_amount(transactions, target_due_date, last_closed_due_date)["total"]


def explain_open_bill_amount(
    transactions: Iterable[dict],
    target_due_date: date,
    last_closed_due_date: Optional[date],
) -> dict:
    """Igual a `compute_open_bill_amount`, mas devolve o rastro por transação.

    `{"target_competencia", "total", "linhas": [{descricao, valor, contou, motivo}]}`.
    Usado no diagnóstico de precisão de fatura por banco (issue #20).
    """
    target_key = _month_key(target_due_date)
    total = Decimal("0")
    linhas: list[dict] = []

    installments: dict[tuple, list[dict]] = {}
    singles: list[dict] = []
    for tx in transactions:
        if _is_payment(tx):
            linhas.append(_linha(tx, Decimal("0"), False, "pagamento de fatura (excluído)"))
            continue
        number, count = _installment_parts(tx)
        if number and count and count > 1:
            installments.setdefault(_purchase_key(tx), []).append(tx)
        else:
            singles.append(tx)

    for tx in singles:
        bill_month = _bill_month(tx, last_closed_due_date, target_key)
        if bill_month == target_key:
            valor = _amount(tx)
            total += valor
            linhas.append(_linha(tx, valor, True, "contou (competência do ciclo)"))
        else:
            linhas.append(
                _linha(tx, Decimal("0"), False, f"outra competência ({bill_month or '—'})")
            )

    for group in installments.values():
        valor, motivo, matched = _installment_detail(group, last_closed_due_date, target_key)
        total += valor
        if matched is not None:
            linhas.append(_linha(matched, valor, True, motivo))
            for tx in group:
                if tx is not matched:
                    linhas.append(_linha(tx, Decimal("0"), False, "outra parcela do parcelamento"))
        elif valor > 0:
            base = group[0]
            linhas.append(_linha(base, valor, True, motivo))
            for tx in group[1:]:
                linhas.append(_linha(tx, Decimal("0"), False, "outra parcela do parcelamento"))
        else:
            for tx in group:
                linhas.append(_linha(tx, Decimal("0"), False, motivo))

    return {
        "target_competencia": target_key,
        "total": total.quantize(Decimal("0.01")),
        "linhas": linhas,
    }


def _linha(tx: dict, valor: Decimal, contou: bool, motivo: str) -> dict:
    meta = _metadata(tx)
    return {
        "descricao": tx.get("description"),
        "data": (tx.get("date") or "")[:10],
        "valor_bruto": str(_amount(tx)),
        "valor": str(valor.quantize(Decimal("0.01"))),
        "contou": contou,
        "motivo": motivo,
        "billForecastDate": meta.get("billForecastDate"),
        "parcela": (
            f"{meta.get('installmentNumber')}/{meta.get('totalInstallments')}"
            if meta.get("installmentNumber")
            else None
        ),
        "status": tx.get("status"),
    }


def _installment_share(
    group: list[dict], last_closed_due_date: Optional[date], target_key: str
) -> Decimal:
    return _installment_detail(group, last_closed_due_date, target_key)[0]


def _installment_detail(
    group: list[dict], last_closed_due_date: Optional[date], target_key: str
) -> tuple[Decimal, str, Optional[dict]]:
    """Quanto deste parcelamento cai na fatura-alvo, com o motivo.

    Uma parcela reemitida aparece duas vezes (uma já dentro de uma fatura
    fechada, outra pendente) — como as duas resolvem para a mesma competência,
    contar uma única vez por competência resolve a duplicata sem precisar
    parear os registros.
    """
    for tx in group:
        if _bill_month(tx, last_closed_due_date, target_key) == target_key:
            return _amount(tx), "parcela deste ciclo (emitida pelo banco)", tx

    # Nenhuma transação para este ciclo: o banco ainda não emitiu a parcela.
    # Projeta a partir da mais recente conhecida, respeitando o total contratado.
    latest = None
    latest_month = None
    for tx in group:
        month = _bill_month(tx, last_closed_due_date, target_key) or _month_key(
            _parse_date(tx.get("date")) or date.min
        )
        if latest_month is None or month > latest_month:
            latest, latest_month = tx, month

    if latest is None or latest_month is None:
        return Decimal("0"), "parcelamento sem competência resolvível", None

    offset = _months_between(latest_month, target_key)
    if offset <= 0:
        return Decimal("0"), "parcelamento não alcança este ciclo", None
    number, count = _installment_parts(latest)
    if number + offset > count:
        return Decimal("0"), "parcelamento já quitado neste ciclo", None
    return _amount(latest), f"parcela {number + offset}/{count} projetada", None


def next_due_date(last_closed_due_date: date, today: Optional[date] = None) -> date:
    """Vencimento do próximo ciclo, mantendo o dia do mês do ciclo anterior.

    Bancos mantêm o dia de vencimento estável (Nubank dia 8, Itaú dia 10), então
    o dia da última fatura fechada é a melhor previsão disponível.
    """
    today = today or date.today()
    year, month = last_closed_due_date.year, last_closed_due_date.month
    while True:
        year, month = _add_months(year, month, 1)
        day = min(last_closed_due_date.day, monthrange(year, month)[1])
        candidate = date(year, month, day)
        if candidate >= today:
            return candidate
