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

# Transferência para terceiros (PIX, TED, boleto) **é** gasto — o dinheiro saiu.
# Listado aqui só para deixar a decisão explícita e evitar que alguém as agrupe
# com as de cima só porque o nome tem "Transfer".
_THIRD_PARTY_TRANSFERS = {
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
    "Digital services": "Lazer",
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
}


def is_transfer(pluggy_category: str | None) -> bool:
    return pluggy_category in TRANSFER_CATEGORIES


def category_name_for(pluggy_category: str | None) -> str | None:
    if not pluggy_category:
        return None
    return PLUGGY_TO_CATEGORY.get(pluggy_category)
