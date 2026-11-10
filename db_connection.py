"""Database connection helpers.

Local development continues to use SQLite.  Deployments that provide
DATABASE_URL use the Supabase PostgreSQL database instead.
"""
import os
import sqlite3

try:
    from psycopg import IntegrityError as PostgresIntegrityError
except ImportError:
    PostgresIntegrityError = sqlite3.IntegrityError

INTEGRITY_ERRORS = (sqlite3.IntegrityError, PostgresIntegrityError)


def using_postgres():
    return bool(os.getenv("DATABASE_URL"))


def connect(path="silvershieldDatabase.db", **kwargs):
    """Open the configured database without putting credentials in source code."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        if os.getenv('RENDER'):
            raise RuntimeError('DATABASE_URL is required on Render; refusing ephemeral SQLite storage')
        return sqlite3.connect(path, **kwargs)

    import psycopg
    class ApplicationCursor(psycopg.Cursor):
        def execute(self, query, params=None, **options):
            if isinstance(query, str) and params is not None:
                query = query.replace('?', '%s')
            return super().execute(query, params, **options)

    return psycopg.connect(database_url, sslmode="require", connect_timeout=10,
                          cursor_factory=ApplicationCursor)


def insert_id(cursor, query, params):
    """Return an inserted primary key on both supported databases."""
    cursor.execute(query + (' RETURNING id' if using_postgres() else ''), params)
    return cursor.fetchone()[0] if using_postgres() else cursor.lastrowid


def initialize_postgres():
    """Create the version-controlled schema in one atomic transaction."""
    from pathlib import Path
    if not using_postgres():
        raise RuntimeError('DATABASE_URL is required for PostgreSQL initialization')
    schema = Path(__file__).with_name('supabase_schema.sql').read_text()
    with connect() as connection:
        connection.execute('SELECT pg_advisory_xact_lock(4902026)')
        connection.execute(schema)


def export_records():
    """Take a consistent snapshot of application tables for administrator backups."""
    import re
    from pathlib import Path
    tables = re.findall(r'CREATE TABLE IF NOT EXISTS (\w+)',
                        Path(__file__).with_name('supabase_schema.sql').read_text())
    data = {}
    with connect() as connection:
        if using_postgres():
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        for table in tables:
            cursor = connection.execute(f'SELECT * FROM {table} ORDER BY id')
            names = [column[0] for column in cursor.description]
            data[table] = [dict(zip(names, row)) for row in cursor.fetchall()]
    return data
