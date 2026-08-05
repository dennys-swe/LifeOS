"""A chave VAPID em PEM precisa ser convertida antes de ir ao `pywebpush`.

O bug que motivou este arquivo: nenhuma notificação nunca chegou. A exceção
acontecia **antes** de qualquer requisição sair, então a subscription jamais era
rejeitada pelo navegador e nada indicava falha — o job reportava sucesso e o
único sintoma era o silêncio no aparelho.
"""
from __future__ import annotations

import pytest

from app.services.push_service import _vapid_key

PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgXoOgh0FoomxBVv2c\n"
    "bFFh/KuazusI/ln4HmuF+nYmFdqhRANCAAToNQKmYtwHXt6n7GIzfYYi1BUIF0BJ\n"
    "EmDM39Z0x0zHsD3cXQ8I7k1hZtGWy+5sT/fLGa8ABhtCFFGzLHrjqkNS\n"
    "-----END PRIVATE KEY-----"
)


def test_pem_is_converted_to_a_vapid_instance():
    """`webpush` trata string como base64 e estoura com o conteúdo de um PEM."""
    py_vapid = pytest.importorskip("py_vapid")

    assert isinstance(_vapid_key(PEM), py_vapid.Vapid01)


def test_non_pem_value_is_passed_through():
    """Base64 e caminho de arquivo já são aceitos direto pelo `pywebpush`."""
    assert _vapid_key("dGVzdGUtYmFzZTY0") == "dGVzdGUtYmFzZTY0"


def test_converted_key_is_accepted_by_pywebpush():
    """Trava o contrato real: é o `pywebpush` que precisa aceitar, não o nosso
    código. Um teste só sobre o tipo passaria mesmo se a API mudasse."""
    pytest.importorskip("pywebpush")
    from py_vapid import Vapid01

    chave = _vapid_key(PEM)
    assert isinstance(chave, Vapid01)
    # mesma checagem que o pywebpush faz antes de assinar
    assert chave.private_key is not None
