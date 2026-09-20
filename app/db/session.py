from collections.abc import Iterator
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from .engine import build_engine

engine = build_engine(settings.database_url)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as db:
        yield db
