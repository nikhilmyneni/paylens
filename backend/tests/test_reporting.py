import ast
import sys
import unittest
import os
from datetime import date
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation import score
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from db import Base
from main import app, get_db
from models import AnalysisRun, Employee


class EvaluationTest(unittest.TestCase):
    def test_wrong_issue_is_binary_hit_but_classification_miss(self):
        result = score(["a", "b", "c", "d"], {"a": "missing_fx", "b": "unexplained_gap", "c": "reviewed_no_action"},
                       [{"target_id": "a", "issue_type": "unexplained_gap"}, {"target_id": "d", "issue_type": "expired_band_used"}])
        self.assertEqual({k: result["metrics"][k] for k in ("tp", "fp", "fn", "tn")}, {"tp": 1, "fp": 1, "fn": 1, "tn": 1})
        gap = next(row for row in result["by_issue"] if row["issue_type"] == "unexplained_gap")
        self.assertEqual((gap["tp"], gap["fp"], gap["fn"]), (0, 1, 1))
        self.assertEqual(len(result["missed_cases"]), 2)

    def test_undefined_metrics_are_not_perfect_scores(self):
        result = score(["a"], {"a": "insufficient_comparators"}, [])
        self.assertIsNone(result["metrics"]["precision"])
        self.assertIsNone(result["metrics"]["recall"])
        self.assertEqual(result["metrics"]["tn"], 1)

    def test_labels_must_join_to_population(self):
        with self.assertRaises(ValueError):
            score(["a"], {}, [{"target_id": "unknown", "issue_type": "missing_fx"}])

    def test_detector_cannot_import_evaluation_or_read_labels(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "analysis.py").read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                self.assertFalse(any(a.name.split(".")[0] in {"evaluation", "reporting", "generate"} for a in node.names))
            if isinstance(node, ast.ImportFrom):
                self.assertNotIn((node.module or "").split(".")[0], {"evaluation", "reporting", "generate"})
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn("ground_truth", node.value.lower())


class ReportingApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(Employee(id="EMP-000001", display_name="Test", hire_date=date(2024, 1, 1), status="active"))
        self.db.add(AnalysisRun(id="RUN-test", as_of=date(2026, 12, 1), ruleset="equity-v1"))
        self.db.commit()
        def session():
            yield self.db
        app.dependency_overrides[get_db] = session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def test_quality_exposes_uncompared_population(self):
        response = self.client.get("/api/v1/quality")
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["coverage"], {"employees": 1, "compared": 0, "excluded": 1, "percent": 0})
        self.assertEqual(report["status"], "attention")

    def test_missing_labels_are_unavailable_not_zero_score(self):
        with patch.dict(os.environ, {"EVALUATION_DATA_DIR": "missing-test-export"}):
            report = self.client.get("/api/v1/evaluation").json()
        self.assertFalse(report["available"])
        self.assertNotIn("metrics", report)

    def test_employee_cannot_access_aggregate_reports(self):
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            for path in ("/api/v1/evaluation", "/api/v1/quality"):
                self.assertEqual(self.client.get(path, headers={"X-Role": "employee"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
