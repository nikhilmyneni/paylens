"""The real generator must satisfy immediate foreign-key constraints."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


def test_generator_inserts_parents_before_dependents():
    generator = Path(__file__).resolve().parents[1] / "generate.py"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        database = root / "seed.db"
        exports = root / "exports"
        result = subprocess.run(
            [sys.executable, str(generator), "--employees", "20", "--database-url",
             "sqlite:///" + database.as_posix(), "--output", str(exports)],
            capture_output=True, text=True, env={**os.environ, "DEMO_MODE": "true"},
        )
        assert result.returncode == 0, result.stderr
        with closing(sqlite3.connect(database)) as connection:
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            assert connection.execute("SELECT count(*) FROM employee").fetchone()[0] == 20
            assert connection.execute("SELECT count(*) FROM salary_record").fetchone()[0] == 720
            assert connection.execute("SELECT count(*) FROM promotion").fetchone()[0] > 0
        report = json.loads((exports / "validation_summary.json").read_text())
        assert report["error_count"] == 0
