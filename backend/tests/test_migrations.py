"""Migrations preserve records and database guards reject history mutation."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from db import initialize_database, normalize_database_url


class MigrationTests(unittest.TestCase):
    def test_adopts_legacy_data_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'legacy.db'}")
            with engine.begin() as connection:
                connection.exec_driver_sql("CREATE TABLE analysis_run (id VARCHAR(40) PRIMARY KEY, as_of DATE NOT NULL, ruleset VARCHAR(30) NOT NULL, created_at DATETIME NOT NULL)")
                connection.exec_driver_sql("INSERT INTO analysis_run VALUES ('legacy', '2026-12-01', 'equity-v1', '2026-12-02')")
            initialize_database(engine)
            initialize_database(engine)
            with engine.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT id FROM analysis_run")).scalar(), "legacy")
                self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar(), "0002_immutable_history")
                self.assertIn("input_checksum", {c["name"] for c in inspect(connection).get_columns("analysis_run")})
            engine.dispose()

    def test_sqlite_history_rejects_update_and_delete(self):
        engine = create_engine("sqlite://")
        initialize_database(engine)
        self._check_guards(engine)
        engine.dispose()

    @unittest.skipUnless(os.getenv("DATABASE_URL", "").startswith(("postgres",)), "PostgreSQL integration URL not configured")
    def test_postgresql_history_guards(self):
        engine = create_engine(normalize_database_url(os.environ["DATABASE_URL"]))
        initialize_database(engine)
        self._check_guards(engine)
        engine.dispose()

    def _check_guards(self, engine):
        # Fixture and every attempted mutation are rolled back, including on CI's
        # seeded PostgreSQL database. The test never deletes existing history.
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("INSERT INTO audit_event (id, actor, action, subject_id, detail, occurred_at) VALUES ('AUD-MIGRATION-TEST', 'test', 'test', 'test', 'test', CURRENT_TIMESTAMP)"))
            for statement in ("UPDATE audit_event SET detail='changed' WHERE id='AUD-MIGRATION-TEST'", "DELETE FROM audit_event WHERE id='AUD-MIGRATION-TEST'"):
                savepoint = connection.begin_nested()
                with self.assertRaises(DBAPIError):
                    connection.execute(text(statement))
                savepoint.rollback()
            self.assertEqual(connection.execute(text("SELECT detail FROM audit_event WHERE id='AUD-MIGRATION-TEST'")).scalar(), "test")
            transaction.rollback()


if __name__ == "__main__":
    unittest.main()
