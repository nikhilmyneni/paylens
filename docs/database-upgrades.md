# Database upgrades

The application uses Alembic revisions instead of relying on `create_all()` to update an existing database.

- `0001_baseline` initializes the frozen first schema, adopts existing prototype tables, adds the nullable analysis input checksum and enforces salary-event uniqueness. It never deletes existing records. Duplicate salary events cause migration failure and require investigation.
- `0002_immutable_history` prevents updates and deletes of salary records, proposal events and audit events in SQLite and PostgreSQL. Corrections are new records.

From `backend/`, run `python bootstrap.py` to migrate without adding demo data, or `python bootstrap.py --seed` to initialize a completely empty database. A database containing employees is preserved. A partially populated database without employees is refused for automatic seeding. Compose runs initialization once before the API starts and persists exports in a separate volume.

For subsequent schema changes, create a new revision with `python -m alembic revision -m "description"`, write explicit upgrade/downgrade operations, and test against both an empty database and an existing fixture. Do not edit the frozen baseline schema to represent future changes.

Startup migrations use a PostgreSQL advisory transaction lock to serialize workers. In a production environment, run migrations under a deployment account and give the runtime account only required data permissions; the current hackathon bootstrap runs both with the configured database credentials. A database owner can disable triggers, so triggers are not a substitute for restricted credentials.

Local checks passed for legacy-data preservation, repeat startup, SQLite history guards, fresh starter seeding and a second seed invocation that preserves the data. CI includes a PostgreSQL-backed migration and history-guard check. PostgreSQL has not been executed locally because this workstation has neither Docker nor a PostgreSQL server installed; CI configuration is not evidence of a completed CI run.

Implementation follows Alembic's [shared-connection migration pattern](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands).
