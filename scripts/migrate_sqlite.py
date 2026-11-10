"""Archive SQLite snapshots and import one live snapshot without overwriting rows.

Run with DATABASE_URL set. Files remain untouched. All writes are atomic.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db_connection import connect, initialize_postgres
from psycopg import sql
from psycopg.types.json import Jsonb


def migrate(paths, live=None):
    initialize_postgres()
    with connect() as target:
        target.execute('CREATE SCHEMA IF NOT EXISTS survey_archive')
        target.execute('''CREATE TABLE IF NOT EXISTS survey_archive.snapshots (
            sha256 TEXT PRIMARY KEY, source TEXT NOT NULL, captured_at TIMESTAMPTZ DEFAULT NOW(),
            records JSONB NOT NULL)''')
        target.execute('ALTER TABLE survey_archive.snapshots ENABLE ROW LEVEL SECURITY')
        for path in paths:
            path = Path(path).resolve()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            source = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
            source.row_factory = sqlite3.Row
            assert source.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            tables = [r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            records = {table: [dict(row) for row in source.execute('SELECT * FROM "'+table.replace('"','""')+'"')] for table in tables}
            source.close()
            target.execute('INSERT INTO survey_archive.snapshots (sha256,source,records) VALUES (?,?,?) ON CONFLICT DO NOTHING',
                           (digest,path.name,Jsonb(records)))
            if live and path == Path(live).resolve():
                for table, rows in records.items():
                    if not rows: continue
                    if target.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]:
                        raise RuntimeError(f'{table} is not empty; refusing to overwrite existing data')
                    column_types = dict(target.execute('SELECT column_name,data_type FROM information_schema.columns WHERE table_schema = current_schema() AND table_name=?',(table,)).fetchall())
                    for row in rows:
                        for key in row:
                            if column_types.get(key) == 'boolean' and row[key] is not None:
                                row[key] = bool(row[key])
                        query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),
                            sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row))
                        target.execute(query,list(row.values()))
                    target.execute(sql.SQL("SELECT setval(pg_get_serial_sequence(%s,'id'), (SELECT MAX(id) FROM {}), true)").format(sql.Identifier(table)),(table,))
            print(path.name, {table:len(rows) for table,rows in records.items() if rows})
    print('Committed snapshots and live import; original SQLite files unchanged')


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('paths',nargs='+')
    parser.add_argument('--live')
    args=parser.parse_args()
    migrate(args.paths,args.live)
