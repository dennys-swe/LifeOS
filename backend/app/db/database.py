from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

DATABASE_URL = settings.database_url

url = make_url(DATABASE_URL)
connect_args = {}

if url.get_backend_name() == "postgresql":
    if "sslmode" not in url.query:
        connect_args = {"sslmode": "require"}
    else:
        connect_args = {"sslmode": url.query["sslmode"]}

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
