from collections import Counter
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import AnalysisIssue, AnalysisRun, Assignment, Band, Comparison, Employee, FxRate, PerformanceEvidence, ProposalEvent, SalaryRecord, SourceDecision

RULESET = "equity-v1"

def money(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def active(rows, on_date):
    matches = [r for r in rows if r.effective_from <= on_date and (r.effective_to is None or on_date <= r.effective_to)]
    if len(matches) != 1:
        raise ValueError(f"expected one effective record, found {len(matches)}")
    return matches[0]

def normalize(monthly, fte, fx=Decimal("1")):
    if Decimal(fte) <= 0 or Decimal(fx) <= 0:
        raise ValueError("FTE and FX must be positive")
    return money(Decimal(monthly) * 12 / Decimal(fte) * Decimal(fx))

def rate_for(rates, currency, on_date):
    if currency == "USD":
        return Decimal("1")
    matches = [r.usd_per_unit for r in rates if r.currency == currency and r.effective_from <= on_date <= r.effective_to]
    if len(matches) != 1:
        raise ValueError(f"expected one {currency}/USD rate on {on_date}, found {len(matches)}")
    return Decimal(matches[0])

def input_rows(as_of: date, db: Session):
    employees = db.scalars(select(Employee)).all()
    assignments = db.scalars(select(Assignment)).all()
    bands = db.scalars(select(Band)).all()
    rates = db.scalars(select(FxRate)).all()
    salaries = db.scalars(select(SalaryRecord).where(SalaryRecord.effective_month <= as_of)).all()
    evidence = db.scalars(select(PerformanceEvidence).where(PerformanceEvidence.period_end <= as_of)).all()
    decisions = db.scalars(select(SourceDecision)).all()
    approval_events = db.scalars(select(ProposalEvent).where(ProposalEvent.next_state == "approved")).all()
    return employees, assignments, bands, rates, salaries, evidence, decisions, approval_events


def fingerprint(rows_by_table):
    # Hash only operational inputs, in canonical order; labels never enter analysis.
    digest = hashlib.sha256()
    for rows in rows_by_table:
        for row in sorted(rows, key=lambda value: value.id):
            values = [getattr(row, column.name) for column in row.__table__.columns]
            digest.update(json.dumps([row.__tablename__, values], default=str, separators=(",", ":")).encode())
    return digest.hexdigest()


def source_checksum(as_of: date, db: Session):
    return fingerprint(input_rows(as_of, db))


def compute(as_of: date, db: Session):
    rows = input_rows(as_of, db)
    employees, assignments, bands, rates, salaries, evidence, decisions, approval_events = rows
    checksum = fingerprint(rows)
    existing = db.scalar(select(AnalysisRun).where(AnalysisRun.as_of == as_of, AnalysisRun.ruleset == RULESET, AnalysisRun.input_checksum == checksum))
    if existing:
        return existing
    run_id = f"RUN-{as_of.isoformat()}-{RULESET}"
    if db.get(AnalysisRun, run_id):
        run_id = f"RUN-{as_of:%Y%m%d}-{checksum[:16]}"
    by_assignment, by_salary, by_evidence, by_decision = {}, {}, {}, {}
    for row in assignments: by_assignment.setdefault(row.employee_id, []).append(row)
    for row in salaries:
        prior = by_salary.get(row.employee_id)
        if prior is None or (row.effective_month, row.event_kind == "adjustment", row.id) > (prior.effective_month, prior.event_kind == "adjustment", prior.id):
            by_salary[row.employee_id] = row
    for row in evidence: by_evidence.setdefault(row.employee_id, []).append(row)
    for row in decisions: by_decision.setdefault(row.employee_id, []).append(row)
    approvals = {}
    for row in approval_events: approvals.setdefault(row.proposal_id, []).append(row)
    group_counts = Counter()
    resolved = {}
    issues = []
    for person in employees:
        sal = by_salary.get(person.id)
        if not sal:
            issues.append((person.id, "missing_salary", "No salary record exists on or before the analysis date."))
            continue
        try: assignment = active(by_assignment.get(person.id, []), sal.effective_month)
        except ValueError as exc:
            issues.append((person.id, "invalid_assignment", f"Assignment cannot be resolved for {sal.effective_month}: {exc}"))
            continue
        key = f"{assignment.role_id}|{assignment.level_id}|{assignment.location_id}"
        group_counts[key] += 1
        resolved[person.id] = (sal, assignment, key)
    previous = db.scalar(select(AnalysisRun).where(AnalysisRun.as_of == as_of).order_by(AnalysisRun.created_at.desc()))
    created_at = datetime.now(timezone.utc)
    if previous:
        previous_time = previous.created_at.replace(tzinfo=timezone.utc) if previous.created_at.tzinfo is None else previous.created_at
        created_at = max(created_at, previous_time + timedelta(microseconds=1))
    db.add(AnalysisRun(id=run_id, as_of=as_of, ruleset=RULESET, input_checksum=checksum, created_at=created_at))
    db.flush()
    for employee_id, issue_type, detail in issues:
        issue_id = "ISS-" + hashlib.sha256(f"{run_id}|{employee_id}|{issue_type}".encode()).hexdigest()[:32]
        db.add(AnalysisIssue(id=issue_id, run_id=run_id, employee_id=employee_id, issue_type=issue_type, detail=detail))
    for person in employees:
        if person.id not in resolved: continue
        sal, assignment, key = resolved[person.id]
        peer_count = group_counts[key]
        annual_local = normalize(sal.monthly_amount, assignment.fte)
        annual = annual_local
        band = None
        matches = [b for b in bands if b.role_id == assignment.role_id and b.level_id == assignment.level_id and b.location_id == assignment.location_id and b.effective_from <= sal.effective_month <= b.effective_to]
        if len(matches) == 1: band = matches[0]
        ratio = position = expected = residual = None
        outcome = "reviewed_no_action"
        explanation = "Pay is within documented factor expectations."
        salary_rate = None
        if not band:
            outcome, explanation = "missing_effective_band", "No unique effective-dated band matches the salary month."
        else:
            try:
                salary_rate = rate_for(rates, sal.currency, sal.effective_month)
                band_rate = rate_for(rates, band.currency, sal.effective_month)
            except ValueError as exc:
                outcome, explanation = "missing_fx_rate", str(exc)
            else:
                annual = normalize(sal.monthly_amount, assignment.fte, salary_rate / band_rate)
                if band.maximum == band.minimum or band.midpoint <= 0:
                    outcome, explanation = "invalid_band", "Band values cannot support compa-ratio and band-position calculations."
                else:
                    ratio = money(annual / band.midpoint)
                    position = money((annual - band.minimum) / (band.maximum - band.minimum))
                    historical_evidence = [e for e in by_evidence.get(person.id, []) if e.period_end <= sal.effective_month]
                    rating = max(historical_evidence, key=lambda e: e.period_end).rating if historical_evidence else 3
                    months = max(1, (sal.effective_month.year - assignment.effective_from.year) * 12 + sal.effective_month.month - assignment.effective_from.month + 1)
                    factor = Decimal("0.88") + Decimal("0.035") * Decimal(rating - 3) + min(Decimal(months), Decimal(60)) * Decimal("0.0015")
                    expected = money(band.midpoint * factor)
                    residual = money((annual - expected) / expected)
                    if peer_count < 5:
                        outcome, explanation = "insufficient_comparators", f"Peer group {key} has {peer_count} employees; minimum is 5."
                    elif annual < band.minimum or annual > band.maximum:
                        outcome, explanation = "pay_outside_band", f"Annual FTE pay {annual} {band.currency} is outside {band.minimum}-{band.maximum}."
                    elif residual < Decimal("-0.12"):
                        outcome, explanation = "unexplained_gap", f"Pay is {abs(residual)*100:.1f}% below expected after rating {rating} and {months} months in level."
        for decision in by_decision.get(person.id, []):
            if decision.salary_id != sal.id: continue
            if decision.reported_band_id and (not band or decision.reported_band_id != band.id):
                outcome, explanation = "expired_band_used", "Source decision referenced a band that was not effective for the salary date."
            elif decision.reported_fte is not None and decision.reported_fte != assignment.fte:
                outcome, explanation = "fte_ignored", "Source decision used an FTE that differs from the effective assignment."
            elif decision.applied_proposal_id and not any(e.occurred_at <= decision.occurred_at for e in approvals.get(decision.applied_proposal_id, [])):
                outcome, explanation = "unapproved_adjustment", "Source decision applied an adjustment without an approved proposal event."
            elif decision.reported_group_key and decision.reported_group_key != key:
                outcome, explanation = "incomparable_group", "Source decision grouped a different role, level, or location without rationale."
            elif decision.applied_proposal_id:
                # An adjustment event is not itself a currency-conversion decision.
                pass
            elif decision.reported_fx is None and sal.currency != "USD":
                outcome, explanation = "missing_fx", "Source decision omitted the currency conversion rate."
            elif decision.reported_fx is not None and salary_rate is not None and sal.currency != "USD" and decision.reported_fx != salary_rate:
                outcome, explanation = "incorrect_fx", "Source decision used a currency conversion rate that was not effective for the salary date."
        db.add(Comparison(id=f"CMP-{run_id}-{person.id}", run_id=run_id, employee_id=person.id, salary_id=sal.id, band_id=band.id if band else None, group_key=key, peer_count=peer_count, annual_fte=annual, compa_ratio=ratio, band_position=position, expected_annual=expected, residual_pct=residual, outcome=outcome, explanation=explanation))
    db.commit()
    return db.get(AnalysisRun, run_id)
