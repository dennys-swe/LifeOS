"""Mapeamento das categorias da Pluggy para as categorias do usuário.

A Pluggy já classifica cada transação (`category`, ex: "Groceries", "Gas
stations") — 96% do extrato real do dono vinha categorizado. Antes disso o
`sync_account` ignorava o campo e dependia só das regras de keyword do usuário,
que estavam vazias: 100% das transações ficaram sem categoria.

O mapeamento é intencionalmente explícito em vez de heurístico: categoria nova
que a Pluggy inventar cai em `None` (sem categoria) em vez de ser adivinhada
errado — e `Transaction.external_category` guarda o valor cru, então dá para
descobrir o que ficou de fora e completar o mapa depois.
"""

from __future__ import annotations

import re
import unicodedata

CREDIT_CARD_PAYMENT = "Credit card payment"

# Dinheiro que apenas muda de lugar — não é consumo. Excluído dos totais de
# gasto para não contar a mesma grana duas vezes (a compra no cartão E a
# quitação da fatura; a saída de uma conta E a entrada na outra).
TRANSFER_CATEGORIES = {
    CREDIT_CARD_PAYMENT,
    "Same person transfer",
    "Transfer - Internal",
    # Aporte não é gasto: o dinheiro continua seu, só trocou de forma.
    "Investments",
    "Mutual funds",
    "Fixed income",
}

# Transferência para terceiros (PIX, TED, boleto) **é** gasto — o dinheiro saiu
# de vez. Não entra em TRANSFER_CATEGORIES, mas também não é consumo, então tem
# categoria própria em vez de ficar sem nenhuma (eram ~21% das transações).
THIRD_PARTY_TRANSFERS = {
    "Transfers",
    "Transfer - PIX",
    "Transfer - TED",
    "Transfer - Cash",
    "Transfer - Bank Slip",
    "Third party transfer - PIX",
    "Third party transfer - TED",
}

# Categoria da Pluggy -> nome da categoria do usuário (ver DEFAULT_CATEGORIES).
PLUGGY_TO_CATEGORY = {
    # Mercado
    "Groceries": "Mercado",
    # Alimentação
    "Eating out": "Alimentação",
    "Food delivery": "Alimentação",
    "Food and drinks": "Alimentação",
    # Transporte
    "Gas stations": "Transporte",
    "Taxi and ride-hailing": "Transporte",
    "Public transportation": "Transporte",
    "Bus tickets": "Transporte",
    "Parking": "Transporte",
    "Vehicle maintenance": "Transporte",
    "Automotive": "Transporte",
    "Car rental": "Transporte",
    "Traffic tickets": "Transporte",
    # Moradia
    "Electricity": "Moradia",
    "Water": "Moradia",
    "Utilities": "Moradia",
    "Housing": "Moradia",
    "Accomodation": "Moradia",
    "Telecommunications": "Moradia",
    "Internet": "Moradia",
    "Houseware": "Moradia",
    # Educação
    "Education": "Educação",
    "School": "Educação",
    "University": "Educação",
    "Bookstore": "Educação",
    "Office supplies": "Educação",
    # Lazer
    "Leisure": "Lazer",
    "Tickets": "Lazer",
    "Travel": "Lazer",
    "Gambling": "Lazer",
    # Saúde
    "Pharmacy": "Saúde",
    "Gyms and fitness centers": "Saúde",
    "Wellness and fitness": "Saúde",
    "Wellness": "Saúde",
    # Compras
    "Shopping": "Compras",
    "Online shopping": "Compras",
    "Clothing": "Compras",
    "Electronics": "Compras",
    # Taxas
    "Bank fees": "Taxas",
    "Credit card fees": "Taxas",
    "Tax on financial operations": "Taxas",
    "Interests charged": "Taxas",
    "Late payment and overdraft costs": "Taxas",
    "Loans and financing": "Taxas",
    # Seguros
    "Insurance": "Seguros",
    # Assinaturas
    "Digital services": "Assinaturas",
    "Streaming": "Assinaturas",
    "Software": "Assinaturas",
}

# Derivado do conjunto acima em vez de repetido à mão: garante que os dois não
# saiam de sincronia se uma variação nova de transferência aparecer.
PLUGGY_TO_CATEGORY.update({nome: "Transferências" for nome in THIRD_PARTY_TRANSFERS})


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
_INCOME_BILL_PAYMENT_ECHO_DESCRIPTION = re.compile(
    r"pagamento\s+com\s+saldo|pagamento\s+on\s*-?\s*line", re.IGNORECASE
)

# Prefixos que a Pluggy/bancos põem antes do nome da contraparte numa entrada.
_INCOMING_TRANSFER_DESCRIPTION = re.compile(
    r"pix\s+recebido|transfer[eê]ncia\s+recebida|ted\s+recebid[ao]|doc\s+recebid[ao]",
    re.IGNORECASE,
)

# Palavras do texto da descrição que não são parte de nome de pessoa.
_NON_NAME_TOKENS = {"PIX", "RECEBIDO", "RECEBIDA", "TRANSFERENCIA", "TED", "DOC", "CP"}


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
    (b) o primeiro nome aparece e **todo** token de nome da descrição pertence
    ao nome cadastrado. "Maria Silva" não casa só por dividir o sobrenome.
    """
    if not description or not user_full_name:
        return False
    if not _INCOMING_TRANSFER_DESCRIPTION.search(description):
        return False
    user_tokens = _name_tokens(user_full_name)
    if not user_tokens:
        return False
    described = [t for t in _name_tokens(description) if t not in _NON_NAME_TOKENS]
    if not described:
        return False
    n = len(user_tokens)
    if any(described[i : i + n] == user_tokens for i in range(len(described) - n + 1)):
        return True
    return user_tokens[0] in described and all(t in user_tokens for t in described)


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


# Ramo Income da Pluggy (`01xxxxxx`). Nunca esteve mapeado: sem destino de
# receita, salário e PIX recebido caíam em categoria de despesa.
PLUGGY_INCOME_TO_CATEGORY = {
    "Salary": "Salário",
    "Retirement": "Salário",
    "Entrepreneurial activities": "Renda extra",
    "Government aid": "Benefícios",
    "Non-recurring income": "Outras receitas",
    "Income": "Outras receitas",
}


def category_name_for(pluggy_category: str | None, is_income: bool = False) -> str | None:
    """Categoria do usuário para uma categoria da Pluggy.

    `is_income` importa porque a mesma categoria da Pluggy significa coisas
    opostas conforme a direção do dinheiro: `Transfers`/`Transfer - PIX` é
    gasto quando você envia (categoria "Transferências") e **receita** quando
    recebe. Sem esse parâmetro, dinheiro recebido era classificado como despesa
    — 202 lançamentos e R$ 58.542,65 nos dados reais do dono.
    """
    if not pluggy_category:
        return None

    if is_income:
        mapped = PLUGGY_INCOME_TO_CATEGORY.get(pluggy_category)
        if mapped:
            return mapped
        # Entrada vinda de transferência de terceiro é dinheiro que entrou de
        # verdade, mas sem natureza declarada — "Outras receitas" é o destino
        # honesto, e não a categoria de gasto de mesmo nome.
        if pluggy_category in THIRD_PARTY_TRANSFERS:
            return "Outras receitas"
        # Sobrou uma categoria de despesa numa entrada. Devolver ela seria pôr
        # receita numa categoria de gasto — foi assim que os repasses semanais
        # da Uber (`Taxi and ride-hailing`, renda de motorista de app) foram
        # parar em "Transporte". A Pluggy classifica pelo estabelecimento, não
        # pela direção, então não dá para distinguir aqui repasse de estorno:
        # o destino honesto é "Outras receitas", e quem quiser precisão cria
        # uma regra de categorização (ex: UBER -> Renda extra).
        return "Outras receitas"

    return PLUGGY_TO_CATEGORY.get(pluggy_category)
