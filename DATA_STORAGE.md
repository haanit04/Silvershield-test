# Survey data storage

Render runs the website. Supabase PostgreSQL stores registered accounts, guest
IDs, consent, survey responses, training attempts, and progress. Configure the
complete PostgreSQL session-pooler URI as `DATABASE_URL` in Render, not just the
database password. Password characters must be URL-encoded. Secrets stay out of Git.

Without DATABASE_URL, local development uses SQLite. On Render, missing or invalid
database configuration fails rather than silently saving to an ephemeral file.
The schema in `supabase_schema.sql` is initialized transactionally and has RLS
enabled. Backend database credentials must never be sent to the browser.

## Backups and migration

Before deploying, download and preserve the current database. Run
`scripts/migrate_sqlite.py --live live.sqlite live.sqlite other-backup.sqlite`
with DATABASE_URL set. This archives all source records under
`survey_archive.snapshots`, identified by source filename and SHA-256. Only the
explicit live snapshot is imported into the application tables; the command
refuses to overwrite populated destination tables. Historical local/test data
remains in the archive instead of silently mixing with current participants.

The authenticated `/admin/download-db` export produces `Survey.json` on PostgreSQL.
Supply DB_DOWNLOAD_TOKEN as the token parameter and keep that URL private. Export
files include account information and password hashes and must be kept private.
Take an independent export after each survey session. Database persistence is not
a guarantee against accidental deletion or loss of access to the account.

## Verification

Run `pytest -q` for local regression tests. With DATABASE_URL set, run
`python scripts/verify_postgres.py` to exercise registration, guest creation,
pre/post surveys, repeated submissions, metrics, and export in a uniquely named
temporary schema. The schema is removed afterwards; production participants are
not modified. Any live deployment smoke-test account must have a `TEST_` prefix
and be excluded from research analysis.

This migration is deployed from the personal `supabase-persistent-surveys` branch;
it does not update the group's existing pull request.
