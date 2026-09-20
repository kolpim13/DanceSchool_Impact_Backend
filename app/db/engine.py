from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url


def build_engine(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() != 'sqlite':
        raise ValueError('This starter is configured for SQLite')
    if parsed.database and parsed.database != ':memory:':
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={'check_same_thread': False, 'timeout': 5})

    @event.listens_for(engine, 'connect')
    def configure(connection, _):
        # SQLAlchemy controls BEGIN consistently, including SELECT and DDL.
        connection.isolation_level = None
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=5000')
        cursor.execute('PRAGMA synchronous=FULL')
        cursor.close()

    @event.listens_for(engine, 'begin')
    def begin(connection):
        connection.exec_driver_sql('BEGIN')

    return engine
