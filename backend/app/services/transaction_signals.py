"""Sinais de classificação de uma transação — fonte única do vocabulário.

Antes viviam três definições de "pagamento de fatura" espalhadas, cada uma
respondendo a uma pergunta **diferente** (issue #167). Elas continuam distintas
de propósito, mas agora nomeadas e no mesmo lugar:

- `is_transfer`: esta transação é dinheiro que só muda de lugar? (exclui dos totais)
- `looks_like_bill_payment`: parece uma quitação de fatura de verdade? Estreita
  de propósito — uma regra ampla reabriria o bug de a cobrança do próprio cartão
  "quitar" a própria fatura (#103).
- `is_card_feed_payment_credit`: no feed do **cartão**, esta linha é pagamento/
  crédito que deve sair da soma da fatura? Ampla e ancorada em `^PAGAMENTO`.
- `is_generic_bill_payment_echo`: eco genérico que não identifica qual fatura foi paga.

Funções puras, sem acesso a banco.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.pluggy_category_map import CREDIT_CARD_PAYMENT, TRANSFER_CATEGORIES

# Categoria da Pluggy para pagamento de fatura no feed do cartão (`categoryId`).
PAYMENT_CATEGORY_ID = "05100000"

# A Pluggy nem sempre marca a quitação de fatura como `Credit card payment`:
# nos dados reais do dono, 13 lançamentos "Pagamento de fatura" vieram como
# `Transfers` genérico. Sem reconhecê-los, a quitação conta como gasto e a
# mesma grana entra duas vezes — a compra no cartão **e** o pagamento da
# fatura. Eram R$ 681,10 em jun+jul/2026, 6,4% do gasto do período.
BILL_PAYMENT_DESCRIPTION = re.compile(r"pagamento\s+(de\s+)?fatura|fatura\s+paga", re.IGNORECASE)

# "Saldo em atraso" é o saldo devedor do rotativo/refinanciamento rolado do
# mês anterior, não um gasto novo — a compra que o originou já entrou como
# gasto quando aconteceu. A Pluggy classifica junto com juros/multa/IOF de
# atraso em "Late payment and overdraft costs" (-> Taxas), e sem distinguir
# pela descrição essa rolagem conta como Taxas nova todo mês (R$ 456,02 de
# R$ 501,85 do card "Taxas" em set/2026 era só esse item).
_OVERDUE_BALANCE_ROLLOVER_DESCRIPTION = re.compile(r"saldo\s+em\s+atraso", re.IGNORECASE)


# Lado de **crédito** do pagamento de fatura: a Pluggy não marca esses ecos
# como `Credit card payment` (só a saída), então entravam como renda. Só vale
# para entrada — `PAGAMENTO COM SALDO` de saída é compra/pagamento de verdade.
#
# Também entram os créditos internos de cartão: `Crédito liberado para Pix` (o cartão
# financiando um Pix, #199) e `Valor adicionado na conta por cartão de crédito` (recarga).
# O dinheiro não é novo; o gasto de verdade está do lado do cartão ou no Pix que sai.
# `cart\S{1,2}o` tolera "cartão" com o til composto ou decomposto.
_INCOME_BILL_PAYMENT_ECHO_DESCRIPTION = re.compile(
    r"pagamento\s+com\s+saldo|pagamento\s+on\s*-?\s*line"
    r"|cr[eé]dito\s+liberado\s+para\s+pix"
    r"|valor\s+adicionado\s+na\s+conta\s+por\s+cart\S{1,2}o",
    re.IGNORECASE,
)

# Prefixos que a Pluggy/bancos põem antes do nome da contraparte numa entrada.
_INCOMING_TRANSFER_DESCRIPTION = re.compile(
    r"pix\s+recebido|transfer[eê]ncia\s+recebida|ted\s+recebid[ao]|doc\s+recebid[ao]",
    re.IGNORECASE,
)

# Palavras do texto da descrição que não são parte de nome de pessoa.
_NON_NAME_TOKENS = {
    "PIX",
    "RECEBIDO",
    "RECEBIDA",
    "TRANSFERENCIA",
    "TED",
    "DOC",
    "CP",
    # Conectivos ("PIX RECEBIDO DE DENNYS", "Marcos da Silva"): não são nome.
    "DE",
    "DA",
    "DO",
    "DAS",
    "DOS",
    "E",
}


def _name_tokens(text: str) -> list[str]:
    """Tokens alfabéticos maiúsculos e sem acento (dígitos/pontuação saem)."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.findall(r"[A-Z]{2,}", ascii_text.upper())


def is_self_transfer_description(description: str | None, user_full_name: str | None) -> bool:
    """Entrada cujo remetente é o próprio usuário (PIX/TED entre contas suas).

    O cadastro e o banco raramente escrevem o nome igual: o banco às vezes manda
    só o primeiro nome (`PIX RECEBIDO Dennys 04/09`) e às vezes o completo
    (`...-Dennys Alves Silva`) para quem cadastrou `Dennys Alves`. Vale se:
    (a) o nome cadastrado aparece inteiro e em sequência na descrição, ou
    (b) a descrição traz **só** o primeiro nome do usuário.
    Nome parcial que não seja só o primeiro ("Maria Silva" para quem cadastrou
    "Maria Alves Silva") fica de fora de propósito: pode ser um parente, e
    tratá-lo como transferência própria esconderia renda de verdade.
    """
    if not description or not user_full_name:
        return False
    if not _INCOMING_TRANSFER_DESCRIPTION.search(description):
        return False
    user_tokens = [t for t in _name_tokens(user_full_name) if t not in _NON_NAME_TOKENS]
    if not user_tokens:
        return False
    described = [t for t in _name_tokens(description) if t not in _NON_NAME_TOKENS]
    if not described:
        return False
    n = len(user_tokens)
    if any(described[i : i + n] == user_tokens for i in range(len(described) - n + 1)):
        return True
    return described == [user_tokens[0]]


def is_transfer(
    pluggy_category: str | None,
    description: str | None = None,
    *,
    is_income: bool = False,
    user_full_name: str | None = None,
) -> bool:
    if pluggy_category in TRANSFER_CATEGORIES:
        return True
    if not description:
        return False
    if BILL_PAYMENT_DESCRIPTION.search(description) or _OVERDUE_BALANCE_ROLLOVER_DESCRIPTION.search(
        description
    ):
        return True
    if is_income:
        return bool(
            _INCOME_BILL_PAYMENT_ECHO_DESCRIPTION.search(description)
            or is_self_transfer_description(description, user_full_name)
        )
    return False


# Nem todo pagamento cai na categoria certa: "PAGAMENTO COM SALDO" (Itaú/Luiza)
# vem como `Transfers`, mesma categoria de créditos legítimos que abatem a
# fatura ("Encerramento de dívida"). A descrição é o que separa os dois.
# Ancorado no início: "PAGAMENTO COM SALDO" / "Pagamento recebido" são quitação;
# "JUROS PAGAMENTO CONTAS" é encargo e não pode ser excluído da fatura.
_CARD_FEED_PAYMENT_DESCRIPTION = re.compile(r"^\s*PAGAMENTO\b", re.IGNORECASE)

# Ecos que não dizem qual fatura foi paga: com mais de um candidato, o que tem
# descrição específica é preferido a esses.
GENERIC_BILL_PAYMENT_ECHOES = {"PAGAMENTO RECEBIDO", "PAGAMENTO COM SALDO", "PAGAMENTO ON LINE"}


def looks_like_bill_payment(external_category: str | None, description: str | None) -> bool:
    """Parece quitação de fatura de verdade (não só cobrança comum do cartão)?"""
    return bool(
        external_category == CREDIT_CARD_PAYMENT
        or BILL_PAYMENT_DESCRIPTION.search(description or "")
    )


def is_card_feed_payment_credit(category_id: str | None, description: str | None) -> bool:
    """Linha do feed do cartão que é pagamento/crédito e sai da soma da fatura."""
    return category_id == PAYMENT_CATEGORY_ID or bool(
        _CARD_FEED_PAYMENT_DESCRIPTION.search(description or "")
    )


def is_generic_bill_payment_echo(description: str | None) -> bool:
    return (description or "").strip().upper() in GENERIC_BILL_PAYMENT_ECHOES
