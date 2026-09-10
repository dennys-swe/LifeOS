from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from app.db.database import _guard_production_db

_NEON = make_url("postgresql+psycopg2://u:p@ep-x-pooler.sa-east-1.aws.neon.tech/db?sslmode=require")
_LOCAL = make_url("postgresql+psycopg2://lifeos:lifeos@localhost:5432/lifeos_dev?sslmode=disable")


def test_blocks_managed_host_outside_production():
    with pytest.raises(RuntimeError, match="banco gerenciado"):
        _guard_production_db(_NEON, environment="development", allow_prod_db=False)


def test_allows_managed_host_in_production():
    _guard_production_db(_NEON, environment="production", allow_prod_db=False)


def test_allows_managed_host_with_opt_in():
    _guard_production_db(_NEON, environment="development", allow_prod_db=True)


def test_ignores_local_host():
    _guard_production_db(_LOCAL, environment="development", allow_prod_db=False)
    _guard_production_db(_LOCAL, environment="staging", allow_prod_db=False)


def test_ignores_sqlite():
    _guard_production_db(
        make_url("sqlite+pysqlite:///:memory:"), environment="development", allow_prod_db=False
    )
