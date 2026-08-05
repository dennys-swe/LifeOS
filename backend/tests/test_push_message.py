"""Texto da notificação de contas vencendo.

O texto anterior era "Você tem 2 conta(s) vencendo em breve: <títulos>" — não
dizia quanto nem quando, e o usuário precisava abrir o app para saber se aquilo
era urgente. As notificações dos próprios bancos, na mesma tela de bloqueio,
trazem valor e data.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.services.push_service import build_notification

HOJE = date(2026, 8, 5)


def _p(titulo, valor, dia):
    return SimpleNamespace(title=titulo, amount=Decimal(str(valor)), due_date=date(2026, 8, dia))


def test_uma_conta_usa_o_titulo_para_a_urgencia():
    n = build_notification([_p("Água", "14.00", 6)], HOJE)

    assert n["title"] == "Água vence amanhã"
    assert n["body"] == "R$ 14,00"


def test_varias_contas_mostram_total_e_prazos():
    n = build_notification(
        [_p("Água", "14.00", 7), _p("Fatura Nubank — 08/2026", "588.37", 8)], HOJE
    )

    assert n["title"] == "2 contas vencendo"
    assert n["body"] == "R$ 602,37 no total · Água (em 07/08), Fatura Nubank (em 08/08)"


def test_competencia_sai_do_rotulo_da_fatura():
    """"— 08/2026" é ruído em algo que vence agora e come o espaço da prévia."""
    n = build_notification([_p("Fatura Nubank — 08/2026", "588.37", 8)], HOJE)

    assert n["title"] == "Fatura Nubank vence em 08/08"


def test_vencimento_de_hoje_e_atrasado_dizem_hoje():
    assert build_notification([_p("Água", "14.00", 5)], HOJE)["title"] == "Água vence hoje"
    # Payable vencido continua sendo cobrança de hoje, não "em 04/08"
    assert build_notification([_p("Água", "14.00", 4)], HOJE)["title"] == "Água vence hoje"


def test_lista_longa_e_truncada():
    contas = [_p(f"Conta {i}", "10.00", 6) for i in range(5)]

    body = build_notification(contas, HOJE)["body"]

    assert body.startswith("R$ 50,00 no total · ")
    assert body.endswith("e mais 2")


def test_valor_usa_formato_brasileiro():
    n = build_notification([_p("Aluguel", "1234.50", 10)], HOJE)

    assert n["body"] == "R$ 1.234,50"


def test_ordem_segue_o_vencimento():
    """A query alimenta `build_notification` já ordenada; a mensagem preserva
    essa ordem. Numa lista truncada em 3, o que fica de fora importa."""
    n = build_notification([_p("Água", "14.00", 7), _p("Fatura Nubank", "588.37", 8)], HOJE)

    assert n["body"].index("Água") < n["body"].index("Fatura Nubank")
