"""Upgrade the local database schema and seed initial records."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.modules.people.models import Person
from app.modules.people.seed import (
    seed_initial_members, seed_roles
)

def main():
    # SQLite requires journal mode to be changed outside a transaction.
    connection = engine.raw_connection()
    try:
        mode = connection.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        if mode.lower() != 'wal':
            raise RuntimeError('Use a file-backed local SQLite database for WAL')
    finally:
        connection.close()

    config = Config(str(ROOT / 'alembic.ini'))
    config.set_main_option('sqlalchemy.url', settings.database_url.replace('%', '%%'))
    command.upgrade(config, 'head')

    with SessionLocal.begin() as db:
        seed_roles(db)
        if db.scalar(select(Person.id).limit(1)) is None:
            seed_initial_members(db)

    print('Database initialized; schema upgraded; WAL enabled; roles seeded')

if __name__ == '__main__':
    main()
