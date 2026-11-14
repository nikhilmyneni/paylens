"""Dataset integrity and deterministic artifact checks.

Run with: python backend/validation.py --database-url sqlite:///./backend/compensation.db
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from db import Base, normalize_database_url
from models import Assignment, Band, Employee, FxRate, PerformanceEvidence, Promotion, ProposalEvent, SalaryRecord, Tenure


def _overlaps(rows, key_fields):
    issues = []
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(getattr(row, field) for field in key_fields)].append(row)
    for key, group in groups.items():
        ordered = sorted(group, key=lambda row: row.effective_from)
        for prev, current in zip(ordered, ordered[1:]):
            if prev.effective_to is None or prev.effective_to >= current.effective_from:
                issues.append({"type": "overlapping_effective_dates", "table": prev.__tablename__, "ids": [prev.id, current.id], "key": key})
    return issues


def validate(db: Session):
    """Return counts and integrity errors; labelled source decisions remain valid input."""
    errors = []
    counts = {}
    for table in Base.metadata.sorted_tables:
        counts[table.name] = db.scalar(select(func.count()).select_from(table))
        primary = list(table.primary_key.columns)
        if len(primary) == 1:
            distinct_count = db.scalar(select(func.count(func.distinct(primary[0]))).select_from(table))
            if distinct_count != counts[table.name]:
                errors.append({"type": "duplicate_primary_key", "table": table.name})
        for column in table.columns:
            for fk in column.foreign_keys:
                parent = fk.column
                child = table.alias("child")
                parent_table = parent.table.alias("parent")
                missing = db.scalar(select(func.count()).select_from(child.outerjoin(parent_table, child.c[column.name] == parent_table.c[parent.name])).where(child.c[column.name].is_not(None), parent_table.c[parent.name].is_(None)))
                if missing:
                    errors.append({"type": "orphan_foreign_key", "table": table.name, "column": column.name, "count": missing})

    assignments = db.scalars(select(Assignment)).all()
    bands = db.scalars(select(Band)).all()
    rates = db.scalars(select(FxRate)).all()
    errors.extend(_overlaps(assignments, ("employee_id",)))
    errors.extend(_overlaps(bands, ("role_id", "level_id", "location_id")))
    errors.extend(_overlaps(rates, ("currency",)))

    salary_keys = Counter((row.employee_id, row.effective_month, row.event_kind) for row in db.scalars(select(SalaryRecord)))
    for key, count in salary_keys.items():
        if count > 1:
            errors.append({"type": "duplicate_salary_event", "key": [str(v) for v in key], "count": count})
    for row in bands:
        if not (0 < row.minimum <= row.midpoint <= row.maximum):
            errors.append({"type": "invalid_band_arithmetic", "id": row.id})
        if row.effective_from > row.effective_to:
            errors.append({"type": "reverse_effective_dates", "id": row.id})
    for row in rates:
        if row.usd_per_unit <= 0 or row.effective_from > row.effective_to:
            errors.append({"type": "invalid_fx_rate", "id": row.id})
    for row in assignments:
        if row.effective_to and row.effective_from > row.effective_to:
            errors.append({"type": "reverse_effective_dates", "id": row.id})
        if not (0 < row.fte <= 1):
            errors.append({"type": "invalid_fte", "id": row.id})

    assignment_by_id = {row.id: row for row in assignments}
    for row in db.scalars(select(Promotion)):
        before, after = assignment_by_id.get(row.from_assignment_id), assignment_by_id.get(row.to_assignment_id)
        if not before or not after or before.employee_id != row.employee_id or after.employee_id != row.employee_id or after.effective_from != row.effective_date or (before.role_id, before.level_id) == (after.role_id, after.level_id):
            errors.append({"type": "invalid_promotion_transition", "id": row.id})

    employees = {row.id: row for row in db.scalars(select(Employee))}
    for row in db.scalars(select(Tenure)):
        person = employees.get(row.employee_id)
        if person and (row.months_in_company < 0 or row.months_in_level < 0 or row.months_in_company < row.months_in_level):
            errors.append({"type": "invalid_tenure", "id": row.id})
    for row in db.scalars(select(PerformanceEvidence)):
        if row.rating not in (1, 2, 3, 4, 5):
            errors.append({"type": "invalid_rating", "id": row.id})

    transitions = {"draft": {"submitted"}, "submitted": {"approved", "rejected"}, "approved": {"applied"}, "rejected": set(), "applied": set()}
    events = defaultdict(list)
    for row in db.scalars(select(ProposalEvent)):
        events[row.proposal_id].append(row)
    for proposal_id, sequence in events.items():
        ordered = sorted(sequence, key=lambda row: (row.occurred_at, row.id))
        previous = None
        for event in ordered:
            valid = (previous is None and event.prior_state is None and event.next_state == "draft") or (previous is not None and event.prior_state == previous and event.next_state in transitions.get(previous, set()))
            if not valid:
                errors.append({"type": "invalid_proposal_transition", "id": event.id, "proposal_id": proposal_id})
            previous = event.next_state
    return {"counts": counts, "error_count": len(errors), "errors": errors}


def checksums(directory):
    """Hash exported data, excluding generated reports so repeated runs compare cleanly."""
    root = Path(directory)
    ignored = {"validation_summary.json", "checksums.json", "manifest.json"}
    return {str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.rglob("*")) if path.is_file() and path.name not in ignored}


def compare_exports(first, second):
    left, right = checksums(first), checksums(second)
    return {"identical": left == right, "left_files": len(left), "right_files": len(right), "mismatches": sorted({name for name in left.keys() | right.keys() if left.get(name) != right.get(name)})}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url")
    parser.add_argument("--compare", nargs=2, metavar=("FIRST", "SECOND"))
    args = parser.parse_args()
    if args.compare:
        print(json.dumps(compare_exports(*args.compare), indent=2))
    elif args.database_url:
        with Session(create_engine(normalize_database_url(args.database_url))) as session:
            result = validate(session)
        print(json.dumps(result, indent=2, default=str))
        raise SystemExit(1 if result["error_count"] else 0)
    else:
        parser.error("provide --database-url or --compare")
