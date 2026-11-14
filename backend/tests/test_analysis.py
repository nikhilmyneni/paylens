"""Behavioral checks for effective-dated compensation comparisons."""

import sys
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from analysis import active, compute, normalize
from db import Base
from models import AdjustmentProposal, AnalysisIssue, AnalysisRun, Assignment, Band, Comparison, Employee, FxRate, Level, Location, PerformanceEvidence, ProposalEvent, Role, SalaryRecord, SourceDecision, Tenure
from validation import validate


class AnalysisRulesTest(unittest.TestCase):
    def test_fte_and_fx_normalization(self):
        self.assertEqual(normalize(Decimal("50000"), Decimal("0.5"), Decimal("0.012")), Decimal("14400.00"))
        with self.assertRaises(ValueError):
            normalize(Decimal("50000"), Decimal("0"))

    def test_effective_date_must_resolve_exactly_once(self):
        first = type("Row", (), {"effective_from": date(2024, 1, 1), "effective_to": date(2024, 12, 31)})()
        second = type("Row", (), {"effective_from": date(2025, 1, 1), "effective_to": None})()
        self.assertIs(active([first, second], date(2024, 12, 31)), first)
        self.assertIs(active([first, second], date(2025, 1, 1)), second)
        with self.assertRaises(ValueError):
            active([first, second], date(2023, 12, 31))
        with self.assertRaises(ValueError):
            active([first, first], date(2024, 6, 1))

    def test_historical_salary_uses_historical_evidence_and_fx(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([
                Role(id="ROLE-01", name="Analyst", family="Data"),
                Level(id="L01", rank=1),
                Location(id="LOC-01", name="US", currency="USD"),
                Band(id="BAND-ROLE-01-L01-LOC-01-2025", role_id="ROLE-01", level_id="L01", location_id="LOC-01", currency="USD", minimum=Decimal("10000"), midpoint=Decimal("15000"), maximum=Decimal("20000"), effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31)),
                FxRate(id="FX-INR-2025", currency="INR", usd_per_unit=Decimal("0.012"), effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31)),
            ])
            for n in range(1, 6):
                employee_id = f"EMP-{n:06d}"
                db.add(Employee(id=employee_id, display_name=f"Synthetic {n}", hire_date=date(2023, 1, 1), status="active"))
                db.add(Assignment(id=f"ASN-{n}", employee_id=employee_id, role_id="ROLE-01", level_id="L01", location_id="LOC-01", effective_from=date(2025, 1, 1), effective_to=None, fte=Decimal("0.5")))
                db.add(SalaryRecord(id=f"SAL-{employee_id}-2025-12", employee_id=employee_id, effective_month=date(2025, 12, 1), monthly_amount=Decimal("50000"), currency="INR", event_kind="baseline"))
                db.add(PerformanceEvidence(id=f"PERF-{n}-early", employee_id=employee_id, period_end=date(2025, 11, 30), rating=3, note="Prior review"))
                db.add(PerformanceEvidence(id=f"PERF-{n}-future", employee_id=employee_id, period_end=date(2025, 12, 31), rating=5, note="Later review"))
                db.add(Tenure(id=f"TEN-{n}", employee_id=employee_id, as_of=date(2026, 1, 1), months_in_company=36, months_in_level=12))
            db.commit()
            run = compute(date(2026, 1, 1), db)
            row = db.scalar(select(Comparison).where(Comparison.run_id == run.id, Comparison.employee_id == "EMP-000001"))
            self.assertEqual(row.annual_fte, Decimal("14400.00"))
            # Rating 3 is the latest evidence available on the 2025-12-01 salary date.
            self.assertEqual(row.expected_annual, Decimal("13470.00"))
            self.assertEqual(row.outcome, "reviewed_no_action")
            self.assertEqual(validate(db)["error_count"], 0)
            db.add(AdjustmentProposal(id="ADJ-2026-000001", comparison_id=row.id, employee_id=row.employee_id, proposed_annual=Decimal("15000"), currency="USD", rationale="Synthetic evidence review", state="draft", version=1, created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))
            db.flush()
            db.add(SourceDecision(id="DEC-1", employee_id=row.employee_id, salary_id=row.salary_id, applied_proposal_id="ADJ-2026-000001", occurred_at=datetime(2026, 1, 10, tzinfo=timezone.utc)))
            db.commit()
            unapproved_run = compute(date(2026, 2, 1), db)
            unapproved = db.scalar(select(Comparison).where(Comparison.run_id == unapproved_run.id, Comparison.employee_id == row.employee_id))
            self.assertEqual(unapproved.outcome, "unapproved_adjustment")
            db.add(ProposalEvent(id="PEV-approval", proposal_id="ADJ-2026-000001", prior_state="submitted", next_state="approved", actor="manager", reason="Documented approval", occurred_at=datetime(2026, 1, 9, tzinfo=timezone.utc)))
            db.commit()
            approved_run = compute(date(2026, 3, 1), db)
            approved = db.scalar(select(Comparison).where(Comparison.run_id == approved_run.id, Comparison.employee_id == row.employee_id))
            self.assertEqual(approved.outcome, "reviewed_no_action")
            # Identical operational inputs reuse an immutable snapshot.
            self.assertEqual(compute(date(2026, 3, 1), db).id, approved_run.id)
            # A same-month adjustment supersedes baseline deterministically.
            db.add(SalaryRecord(id="SAL-adjustment", employee_id=row.employee_id, effective_month=date(2025, 12, 1), monthly_amount=Decimal("60000"), currency="INR", event_kind="adjustment"))
            db.commit()
            rerun = compute(date(2026, 3, 1), db)
            self.assertNotEqual(rerun.id, approved_run.id)
            self.assertNotEqual(rerun.input_checksum, approved_run.input_checksum)
            self.assertIsNotNone(db.get(AnalysisRun, approved_run.id))
            revised = db.scalar(select(Comparison).where(Comparison.run_id == rerun.id, Comparison.employee_id == row.employee_id))
            self.assertEqual(revised.salary_id, "SAL-adjustment")
            self.assertEqual(revised.annual_fte, Decimal("17280.00"))

    def test_unassessable_employees_have_explicit_coverage_issues(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            db.add_all([
                Employee(id="EMP-000001", display_name="Missing salary", hire_date=date(2024, 1, 1), status="active"),
                Employee(id="EMP-000002", display_name="Missing assignment", hire_date=date(2024, 1, 1), status="active"),
                SalaryRecord(id="SAL-2", employee_id="EMP-000002", effective_month=date(2026, 1, 1), monthly_amount=Decimal("1000"), currency="USD", event_kind="baseline"),
            ])
            db.commit()
            run = compute(date(2026, 1, 1), db)
            issues = db.scalars(select(AnalysisIssue).where(AnalysisIssue.run_id == run.id)).all()
            self.assertEqual({item.issue_type for item in issues}, {"missing_salary", "invalid_assignment"})
            self.assertEqual({item.employee_id for item in issues}, {"EMP-000001", "EMP-000002"})

    def test_source_detectors_normal_and_failure_cases(self):
        cases = [
            ({"reported_fx": Decimal("0.012")}, "reviewed_no_action"),
            ({"reported_band_id": "BAND", "reported_fx": Decimal("0.012")}, "reviewed_no_action"),
            ({"reported_fte": Decimal("0.5"), "reported_fx": Decimal("0.012")}, "reviewed_no_action"),
            ({"reported_group_key": "ROLE|L01|LOC", "reported_fx": Decimal("0.012")}, "reviewed_no_action"),
            ({"reported_band_id": "BAND-OLD"}, "expired_band_used"),
            ({"reported_fte": Decimal("1")}, "fte_ignored"),
            ({"reported_fte": Decimal("0")}, "fte_ignored"),
            ({"reported_group_key": "OTHER|L01|LOC"}, "incomparable_group"),
            ({}, "missing_fx"),
            ({"reported_fx": Decimal("0.020")}, "incorrect_fx"),
        ]
        for decision_values, expected in cases:
            with self.subTest(expected=expected):
                engine = create_engine("sqlite:///:memory:")
                Base.metadata.create_all(engine)
                with Session(engine) as db:
                    db.add_all([
                        Role(id="ROLE", name="Analyst", family="Data"), Level(id="L01", rank=1), Location(id="LOC", name="US", currency="USD"),
                        FxRate(id="FX", currency="INR", usd_per_unit=Decimal("0.012"), effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31)),
                    ])
                    for year, bid in [(2025, "BAND-OLD"), (2026, "BAND")]:
                        db.add(Band(id=bid, role_id="ROLE", level_id="L01", location_id="LOC", currency="USD", minimum=Decimal("10000"), midpoint=Decimal("15000"), maximum=Decimal("20000"), effective_from=date(year, 1, 1), effective_to=date(year, 12, 31)))
                    for n in range(5):
                        eid = f"EMP-{n:06d}"
                        db.add(Employee(id=eid, display_name=eid, hire_date=date(2025, 1, 1), status="active"))
                        db.add(Assignment(id=f"ASN-{n}", employee_id=eid, role_id="ROLE", level_id="L01", location_id="LOC", effective_from=date(2026, 1, 1), effective_to=None, fte=Decimal("0.5")))
                        db.add(SalaryRecord(id=f"SAL-{n}", employee_id=eid, effective_month=date(2026, 1, 1), monthly_amount=Decimal("50000"), currency="INR", event_kind="baseline"))
                    db.flush()
                    db.add(SourceDecision(id="DEC", employee_id="EMP-000000", salary_id="SAL-0", occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc), **decision_values))
                    db.commit()
                    run = compute(date(2026, 1, 1), db)
                    result = db.scalar(select(Comparison).where(Comparison.run_id == run.id, Comparison.employee_id == "EMP-000000"))
                    self.assertEqual(result.outcome, expected)
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
