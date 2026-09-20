"""Create/migrate database, enable WAL and seed predefined roles."""
import sys
from pathlib import Path
from alembic import command
from alembic.config import Config
from app.db.session import engine, SessionLocal
from app.modules.people.seed import (
    seed_initial_members, seed_roles
)
#========================================================

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
#========================================================

def main():
    # Raw DBAPI connection: journal mode must be changed outside a transaction.
    connection = engine.raw_connection()
    try:
        mode = connection.execute('PRAGMA journal_mode=WAL').fetchone()[0]
        if mode != 'wal':
            raise RuntimeError('Use a file-backed local SQLite database for WAL')
    finally:
        connection.close()

    command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
    with SessionLocal.begin() as db:
        seed_roles(db)
        seed_initial_members(db)

    print('Database created; WAL enabled; roles seeded; initial members seeded')
#========================================================

if __name__ == '__main__':
    main()
