import pytest
import db_connection


def test_render_refuses_ephemeral_fallback(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setenv('RENDER', 'true')
    with pytest.raises(RuntimeError, match='refusing ephemeral'):
        db_connection.connect(':memory:')


def test_local_sqlite_still_supported(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('RENDER', raising=False)
    with db_connection.connect(':memory:') as connection:
        connection.execute('CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)')
        inserted = db_connection.insert_id(connection.cursor(),
            'INSERT INTO sample (value) VALUES (?)', ('kept',))
        assert connection.execute('SELECT value FROM sample WHERE id=?', (inserted,)).fetchone() == ('kept',)
