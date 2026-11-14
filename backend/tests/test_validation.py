"""Exercise validation against broken imported records, beyond DB constraints."""
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from db import Base
import models  # Register all tables before creating fixtures.
from validation import _overlaps, validate


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        # Imported corruption must be reported even if the import bypassed constraints.
        self.db.execute(text("PRAGMA foreign_keys=OFF"))
        self.db.execute(text("PRAGMA ignore_check_constraints=ON"))

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_valid_empty_database(self):
        self.assertEqual(validate(self.db)["error_count"], 0)

    def test_orphan_salary_is_detected(self):
        self.db.add(models.SalaryRecord(id="SAL-orphan", employee_id="EMP-missing", effective_month=date(2026, 1, 1), monthly_amount=100, currency="USD", event_kind="baseline"))
        self.db.flush()
        self.assertTrue(any(e["type"] == "orphan_foreign_key" and e["table"] == "salary_record" for e in validate(self.db)["errors"]))

    def test_band_arithmetic_and_reversed_dates(self):
        self.db.add(models.Band(id="BAND-broken", role_id="missing", level_id="missing", location_id="missing", currency="USD", minimum=200, midpoint=100, maximum=300, effective_from=date(2026, 12, 1), effective_to=date(2026, 1, 1)))
        self.db.flush()
        kinds = {e["type"] for e in validate(self.db)["errors"]}
        self.assertTrue({"invalid_band_arithmetic", "reverse_effective_dates"}.issubset(kinds))

    def test_invalid_fte_and_fx(self):
        self.db.add(models.Assignment(id="ASN-broken", employee_id="missing", role_id="missing", level_id="missing", location_id="missing", effective_from=date(2026, 1, 1), effective_to=None, fte=0))
        self.db.add(models.FxRate(id="FX-broken", currency="EUR", usd_per_unit=-1, effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31)))
        self.db.flush()
        kinds = {e["type"] for e in validate(self.db)["errors"]}
        self.assertTrue({"invalid_fte", "invalid_fx_rate"}.issubset(kinds))

    def test_approval_skip_is_detected(self):
        self.db.add(models.ProposalEvent(id="EVT-1", proposal_id="missing", prior_state=None, next_state="draft", actor="test", reason="fixture", occurred_at=datetime(2026, 1, 1)))
        self.db.add(models.ProposalEvent(id="EVT-2", proposal_id="missing", prior_state="draft", next_state="applied", actor="test", reason="fixture", occurred_at=datetime(2026, 1, 2)))
        self.db.flush()
        self.assertTrue(any(e["type"] == "invalid_proposal_transition" for e in validate(self.db)["errors"]))

    def test_adjacent_dates_are_valid_shared_day_is_overlap(self):
        def row(id, start, end):
            return SimpleNamespace(id=id, employee_id="EMP-1", effective_from=start, effective_to=end, __tablename__="employee_assignment")
        first = row("a", date(2026, 1, 1), date(2026, 1, 31))
        valid = row("b", date(2026, 2, 1), None)
        invalid = row("c", date(2026, 1, 31), None)
        self.assertEqual(_overlaps([first, valid], ("employee_id",)), [])
        self.assertEqual(len(_overlaps([first, invalid], ("employee_id",))), 1)


if __name__ == "__main__":
    unittest.main()
