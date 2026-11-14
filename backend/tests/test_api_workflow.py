"""Exercise the proposal approval path through the public API."""

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from db import Base
from main import app, event, get_db
from models import AdjustmentProposal, AnalysisRun, Assignment, AuditEvent, Band, Comparison, Employee, Level, Location, ProposalEvent, Role, SalaryRecord


class ProposalWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            Role(id="ROL-01", name="Analyst", family="Data"),
            Level(id="L01", rank=1),
            Location(id="LOC-US", name="Austin", currency="USD"),
            Employee(id="EMP-000001", display_name="Synthetic 1", hire_date=date(2024, 1, 1), status="active"),
            Assignment(id="ASN-1", employee_id="EMP-000001", role_id="ROL-01", level_id="L01", location_id="LOC-US", effective_from=date(2024, 1, 1), effective_to=None, fte=Decimal("0.5")),
            Band(id="BAND-ROL-01-L01-LOC-US-2026", role_id="ROL-01", level_id="L01", location_id="LOC-US", currency="USD", minimum=Decimal("80000"), midpoint=Decimal("100000"), maximum=Decimal("125000"), effective_from=date(2026, 1, 1), effective_to=date(2026, 12, 31)),
            SalaryRecord(id="SAL-EMP-000001-2026-12", employee_id="EMP-000001", effective_month=date(2026, 12, 1), monthly_amount=Decimal("3500"), currency="USD", event_kind="baseline"),
            AnalysisRun(id="RUN-2026-12-01-equity-v1", as_of=date(2026, 12, 1), ruleset="equity-v1"),
        ])
        self.db.flush()
        self.db.add(Comparison(id="CMP-1", run_id="RUN-2026-12-01-equity-v1", employee_id="EMP-000001", salary_id="SAL-EMP-000001-2026-12", band_id="BAND-ROL-01-L01-LOC-US-2026", group_key="ROL-01|L01|LOC-US", peer_count=6, annual_fte=Decimal("84000"), compa_ratio=Decimal("0.84"), band_position=Decimal("0.08"), expected_annual=Decimal("90000"), residual_pct=Decimal("-0.07"), outcome="reviewed_no_action", explanation="Synthetic fixture"))
        self.db.commit()

        def override_db():
            yield self.db

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def create_proposal(self):
        response = self.client.post("/api/v1/proposals", json={"comparison_id": "CMP-1", "proposed_annual": "95000", "rationale": "Documented compensation review"}, headers={"X-Role": "hr"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    def test_approve_then_apply_adds_salary_event_once(self):
        pid = self.create_proposal()
        submitted = self.client.post(f"/api/v1/proposals/{pid}/submit", json={"version": 1, "reason": "Submit for manager review"}, headers={"X-Role": "hr"})
        self.assertEqual(submitted.status_code, 200, submitted.text)
        approved = self.client.post(f"/api/v1/proposals/{pid}/decision", json={"version": 2, "reason": "Evidence supports adjustment", "decision": "approved"}, headers={"X-Role": "manager"})
        self.assertEqual(approved.status_code, 200, approved.text)
        applied = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 3, "reason": "Apply approved change"}, headers={"X-Role": "hr"})
        self.assertEqual(applied.status_code, 200, applied.text)
        salary = self.db.get(SalaryRecord, applied.json()["salary_id"])
        self.assertEqual(salary.event_kind, "adjustment")
        self.assertEqual(salary.monthly_amount, Decimal("3958.33"))
        self.assertEqual(self.db.get(AdjustmentProposal, pid).state, "applied")
        again = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 4, "reason": "Apply approved change"}, headers={"X-Role": "hr"})
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SalaryRecord).where(SalaryRecord.event_kind == "adjustment")), 1)

    def test_draft_or_rejected_proposal_cannot_be_applied(self):
        pid = self.create_proposal()
        denied = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 1, "reason": "Attempt before approval"}, headers={"X-Role": "hr"})
        self.assertEqual(denied.status_code, 409)
        self.assertEqual(self.db.get(AdjustmentProposal, pid).state, "draft")
        self.assertEqual(self.db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.action == "proposal.apply_denied")), 1)
        self.client.post(f"/api/v1/proposals/{pid}/submit", json={"version": 1, "reason": "Submit for manager review"}, headers={"X-Role": "hr"})
        rejected = self.client.post(f"/api/v1/proposals/{pid}/decision", json={"version": 2, "reason": "Insufficient evidence", "decision": "rejected"}, headers={"X-Role": "manager"})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        denied_again = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 3, "reason": "Attempt after rejection"}, headers={"X-Role": "hr"})
        self.assertEqual(denied_again.status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(SalaryRecord).where(SalaryRecord.event_kind == "adjustment")), 0)

    def approve(self, pid):
        self.client.post(f"/api/v1/proposals/{pid}/submit", json={"version": 1, "reason": "Submit for review"}, headers={"X-Role": "hr"})
        response = self.client.post(f"/api/v1/proposals/{pid}/decision", json={"version": 2, "reason": "Evidence accepted", "decision": "approved"}, headers={"X-Role": "manager"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_ids_are_sequential_and_stale_transition_appends_no_event(self):
        first, second = self.create_proposal(), self.create_proposal()
        self.assertEqual(first, "ADJ-2026-000001")
        self.assertEqual(second, "ADJ-2026-000002")
        self.approve(first)
        count = self.db.scalar(select(func.count()).select_from(ProposalEvent))
        stale = self.client.post(f"/api/v1/proposals/{first}/decision", json={"version": 2, "reason": "Stale rejection", "decision": "rejected"}, headers={"X-Role": "manager"})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ProposalEvent)), count)

    def test_effective_date_resolves_future_assignment_fte(self):
        current = self.db.get(Assignment, "ASN-1")
        current.effective_to = date(2027, 1, 31)
        self.db.add(Assignment(id="ASN-2", employee_id="EMP-000001", role_id="ROL-01", level_id="L01", location_id="LOC-US", effective_from=date(2027, 2, 1), effective_to=None, fte=Decimal("1")))
        self.db.commit()
        pid = self.create_proposal()
        self.approve(pid)
        response = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 3, "reason": "Apply February change", "effective_date": "2027-02-01"}, headers={"X-Role": "hr"})
        self.assertEqual(response.status_code, 200, response.text)
        salary = self.db.get(SalaryRecord, response.json()["salary_id"])
        self.assertEqual(salary.effective_month, date(2027, 2, 1))
        self.assertEqual(salary.monthly_amount, Decimal("7916.67"))

    def test_effective_date_must_follow_analysis_and_be_month_start(self):
        pid = self.create_proposal()
        self.approve(pid)
        for invalid in ["2026-12-01", "2027-01-15"]:
            response = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 3, "reason": "Invalid date test", "effective_date": invalid}, headers={"X-Role": "hr"})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.get(AdjustmentProposal, pid).state, "approved")

    def test_role_change_requires_new_review_before_application(self):
        self.db.add(Role(id="ROL-02", name="Engineer", family="Engineering"))
        self.db.get(Assignment, "ASN-1").effective_to = date(2026, 12, 31)
        self.db.add(Assignment(id="ASN-new-role", employee_id="EMP-000001", role_id="ROL-02", level_id="L01", location_id="LOC-US", effective_from=date(2027, 1, 1), effective_to=None, fte=Decimal("1")))
        self.db.commit()
        pid = self.create_proposal()
        self.approve(pid)
        response = self.client.post(f"/api/v1/proposals/{pid}/apply", json={"version": 3, "reason": "Apply after promotion"}, headers={"X-Role": "hr"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("new compensation review", response.json()["detail"])
        self.assertEqual(self.db.get(AdjustmentProposal, pid).state, "approved")

    def test_role_and_production_token_denials(self):
        denied = self.client.get("/api/v1/comparisons", headers={"X-Role": "employee"})
        self.assertEqual(denied.status_code, 403)
        denied_create = self.client.post("/api/v1/proposals", json={"comparison_id": "CMP-1", "proposed_annual": "95000", "rationale": "Documented compensation review"}, headers={"X-Role": "manager"})
        self.assertEqual(denied_create.status_code, 403)
        with patch.dict("os.environ", {"DEMO_MODE": "false", "ROLE_TOKENS": '{"hr":"test-secret"}'}):
            self.assertEqual(self.client.get("/api/v1/summary").status_code, 401)
            self.assertEqual(self.client.get("/api/v1/summary", headers={"X-Role": "hr", "X-API-Key": "test-secret"}).status_code, 200)

    def test_atomic_transition_rejects_second_session_stale_snapshot(self):
        pid = self.create_proposal()
        with Session(self.engine) as stale_db:
            stale = stale_db.get(AdjustmentProposal, pid)
            self.assertEqual(stale.version, 1)
            submitted = self.client.post(f"/api/v1/proposals/{pid}/submit", json={"version": 1, "reason": "First submission wins"}, headers={"X-Role": "hr"})
            self.assertEqual(submitted.status_code, 200)
            with self.assertRaises(HTTPException) as caught:
                event(stale_db, stale, "submitted", {"name": "second-reviewer"}, "Concurrent stale submission")
            self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(self.db.scalar(select(func.count()).select_from(ProposalEvent).where(ProposalEvent.proposal_id == pid, ProposalEvent.next_state == "submitted")), 1)


if __name__ == "__main__":
    unittest.main()
