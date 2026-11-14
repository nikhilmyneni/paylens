"""Fixed-seed synthetic compensation dataset. No real employee data is used."""
import argparse
import csv
import hashlib
import json
import os
import random
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from sqlalchemy import create_engine, inspect, select, func
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from db import Base, normalize_database_url, initialize_database
from models import (AdjustmentProposal, AnalysisIssue, AnalysisRun, Assignment, Band, Comparison, Employee, FxRate, IdCounter, Level,
                    Location, PerformanceEvidence, Promotion, ProposalEvent, Role,
                    SalaryRecord, SourceDecision, Tenure)

SEED = 20261022
AS_OF = date(2026, 12, 1)
FIXED_TIME = datetime(2026, 12, 2, tzinfo=timezone.utc)
LOCATIONS = [("LOC-IN", "Hyderabad", "INR", Decimal("0.012"), Decimal("450000")),
             ("LOC-US", "Austin", "USD", Decimal("1"), Decimal("68000")),
             ("LOC-EU", "Berlin", "EUR", Decimal("1.08"), Decimal("59000"))]

def month(year, index):
    return date(year + index // 12, index % 12 + 1, 1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=["starter", "full"], default="starter")
    parser.add_argument("--employees", type=int, default=None)
    parser.add_argument("--database-url", default="sqlite:///./compensation.db")
    parser.add_argument("--output", default="../data/starter")
    parser.add_argument("--replace", action="store_true", help="Replace an existing disposable synthetic database")
    args = parser.parse_args()
    count = args.employees or (5000 if args.scale == "full" else 240)
    rng = random.Random(SEED)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    engine = create_engine(normalize_database_url(args.database_url))
    existing = set(inspect(engine).get_table_names())
    if "employee" in existing:
        with Session(engine) as check_session:
            has_rows = check_session.scalar(select(func.count()).select_from(Employee)) > 0
        if has_rows and not args.replace:
            raise SystemExit("Database already contains employees; use --replace only for a disposable synthetic database")
    if args.replace and os.getenv("DEMO_MODE", "true").lower() != "true":
        raise SystemExit("--replace is allowed only in DEMO_MODE=true")
    if args.replace:
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    Base.metadata.create_all(engine)
    initialize_database(engine)
    roles = [Role(id=f"ROL-{i:02d}", name=f"{family} {i//4+1}", family=family) for i, family in enumerate(["Engineering", "Data", "Product", "Security"] * 5)]
    # Names must be unique even when a family occurs several times.
    for i, role in enumerate(roles): role.name = f"{role.family} Specialist {i+1}"
    levels = [Level(id=f"L{i:02d}", rank=i) for i in range(1, 11)]
    locs = [Location(id=x[0], name=x[1], currency=x[2]) for x in LOCATIONS]
    bands, rates = [], []
    for year in (2024, 2025, 2026):
        for loc_id, _, currency, fx, base in LOCATIONS:
            rates.append(FxRate(id=f"FX-{currency}-{year}", currency=currency, usd_per_unit=fx, effective_from=date(year, 1, 1), effective_to=date(year, 12, 31)))
            for ri, role in enumerate(roles):
                for level in levels:
                    midpoint = (base * (Decimal("1.20") ** (level.rank - 1)) * (Decimal("1") + Decimal(ri % 5) * Decimal("0.025")) * (Decimal("1.035") ** (year-2024))).quantize(Decimal("0.01"))
                    bands.append(Band(id=f"BAND-{role.id}-{level.id}-{loc_id}-{year}", role_id=role.id, level_id=level.id, location_id=loc_id, currency=currency, minimum=(midpoint * Decimal("0.78")).quantize(Decimal("0.01")), midpoint=midpoint, maximum=(midpoint * Decimal("1.25")).quantize(Decimal("0.01")), effective_from=date(year, 1, 1), effective_to=date(year, 12, 31)))
    band_map = {(b.role_id, b.level_id, b.location_id, b.effective_from.year): b for b in bands}
    employees, assignments, salary, performance, tenure, promotions = [], [], [], [], [], []
    outliers = set(range(1, count+1, max(40, count//75)))
    truth = []
    with Session(engine) as db:
        db.add_all(roles + levels + locs + bands + rates)
        db.flush()
        for i in range(1, count+1):
            eid = f"EMP-{i:06d}"
            role_idx = (i-1) % (200 if count >= 1000 else 8)
            role = roles[role_idx // 10]
            level_rank = role_idx % 10 + 1
            loc_idx = (i-1) % 3
            hire_year = rng.randint(2016, 2023)
            hire = date(hire_year, rng.randint(1,12), 1)
            person = Employee(id=eid, display_name=f"Employee {i:06d}", hire_date=hire, status="active")
            employees.append(person)
            ratings = {year: rng.choices([1,2,3,4,5], weights=[3,10,51,28,8])[0] for year in (2024,2025,2026)}
            if i in outliers: ratings[2026] = 4
            for year, rating in ratings.items():
                performance.append(PerformanceEvidence(id=f"PERF-{eid}-{year}", employee_id=eid, period_end=date(year-1, 12, 31), rating=rating, note="Synthetic calibrated annual review"))
            cut = 13 if i % 9 == 0 else (25 if i % 13 == 0 else None)
            assignment_specs = [(0, cut-1 if cut else 35, level_rank, loc_idx, Decimal("0.5") if i % 17 == 0 or i == 3 else Decimal("1"))]
            if cut is not None:
                new_level = min(10, level_rank+1) if i % 9 == 0 else level_rank
                new_loc = (loc_idx+1)%3 if i % 13 == 0 else loc_idx
                new_fte = Decimal("0.8") if i % 17 == 0 else (Decimal("0.5") if i == 3 else Decimal("1"))
                assignment_specs.append((cut, 35, new_level, new_loc, new_fte))
            own_assignments = []
            for ai, (start, end, lr, li, fte) in enumerate(assignment_specs):
                aid = f"ASN-{eid}-{ai+1:02d}"
                row = Assignment(id=aid, employee_id=eid, role_id=role.id, level_id=f"L{lr:02d}", location_id=LOCATIONS[li][0], effective_from=month(2024,start), effective_to=month(2024,end+1) if end < 35 else None, fte=fte)
                # End dates are exclusive boundaries represented as previous day.
                if end < 35:
                    next_start = month(2024,end+1)
                    row.effective_to = date.fromordinal(next_start.toordinal()-1)
                own_assignments.append(row)
                assignments.append(row)
            if cut is not None and i % 9 == 0 and level_rank < 10:
                promotions.append(Promotion(id=f"PROM-{eid}-{month(2024,cut).year}", employee_id=eid, from_assignment_id=own_assignments[0].id, to_assignment_id=own_assignments[1].id, effective_date=month(2024,cut), reason="Documented level progression"))
            months_company = (AS_OF.year - hire.year)*12 + AS_OF.month-hire.month
            last_assignment = own_assignments[-1]
            months_level = (AS_OF.year-last_assignment.effective_from.year)*12+AS_OF.month-last_assignment.effective_from.month
            tenure.append(Tenure(id=f"TEN-{eid}-2026-12", employee_id=eid, as_of=AS_OF, months_in_company=months_company, months_in_level=months_level))
            variation = Decimal(str(round(rng.gauss(0, 0.045), 5)))
            for m in range(36):
                d = month(2024,m)
                a = own_assignments[1] if cut is not None and m >= cut else own_assignments[0]
                b = band_map[(a.role_id,a.level_id,a.location_id,d.year)]
                tenure_months = max(0, (d.year-a.effective_from.year)*12+d.month-a.effective_from.month)
                factor = Decimal("0.88") + Decimal("0.035")*Decimal(ratings[d.year]-3) + min(Decimal(tenure_months),Decimal(60))*Decimal("0.0015") + variation
                if i in outliers and d.year == 2026: factor = Decimal("0.80")
                annual = b.midpoint * factor * a.fte
                monthly_amount = (annual/12).quantize(Decimal("0.01"))
                salary.append(SalaryRecord(id=f"SAL-{eid}-{d.year}-{d.month:02d}", employee_id=eid, effective_month=d, monthly_amount=monthly_amount, currency=b.currency, event_kind="promotion" if cut == m and i%9==0 else "baseline"))
            if i in outliers:
                truth.append({"target_id": eid, "issue_type":"unexplained_gap", "expected_decision":"review", "reason":"2026 pay set to 80% of band midpoint despite documented rating 4"})
        db.add_all(employees + assignments + promotions + salary + performance + tenure)
        db.flush()
        source = []
        def decision(index, **kwargs):
            eid = f"EMP-{index:06d}"
            return SourceDecision(id=f"DEC-{eid}", employee_id=eid, salary_id=f"SAL-{eid}-2026-12", occurred_at=FIXED_TIME, **kwargs)
        # Five deliberate faulty source decisions; the input contains the action, not its label.
        if count >= 10:
            for idx, kind, fields in [
                (2, "expired_band_used", {"reported_band_id": band_map[(assignments[1].role_id, assignments[1].level_id, assignments[1].location_id, 2025)].id}),
                (3, "fte_ignored", {"reported_fte": Decimal("1")}),
                (4, "missing_fx", {}),
                (5, "incomparable_group", {"reported_group_key": "ROL-99|L99|LOC-US"}),
            ]:
                source.append(decision(idx, **fields))
                truth.append({"target_id":f"EMP-{idx:06d}","issue_type":kind,"expected_decision":"exception","reason":"Injected faulty source decision"})
            db.add_all(source)
        db.commit()
    if count >= 10:
        from analysis import compute
        with Session(engine) as db:
            run = compute(date(2026, 11, 1), db)
            run.created_at = FIXED_TIME
            comparison = db.get(Comparison, f"CMP-{run.id}-EMP-000006")
            proposal = AdjustmentProposal(id="ADJ-2026-000001", comparison_id=comparison.id, employee_id="EMP-000006", proposed_annual=comparison.annual_fte * Decimal("1.08"), currency="EUR", rationale="Synthetic draft recorded as applied by a source system", state="draft", version=1, created_at=FIXED_TIME)
            db.add(proposal)
            db.flush()
            db.add(ProposalEvent(id="PEV-ADJ-2026-000001-01", proposal_id=proposal.id, prior_state=None, next_state="draft", actor="synthetic-import", reason="Draft created", occurred_at=FIXED_TIME))
            db.add(SourceDecision(id="DEC-EMP-000006", employee_id="EMP-000006", salary_id="SAL-EMP-000006-2026-12", applied_proposal_id=proposal.id, occurred_at=FIXED_TIME))
            db.commit()
        truth.append({"target_id":"EMP-000006","issue_type":"unapproved_adjustment","expected_decision":"exception","reason":"Source applied a draft proposal without approval"})
        with Session(engine) as db:
            run = compute(AS_OF, db)
            run.created_at = FIXED_TIME
            db.commit()
    # Export in parent-first order. Ground truth lives outside the importable inputs directory.
    table_order = [Role, Level, Location, Employee, Assignment, Band, FxRate, SalaryRecord, PerformanceEvidence, Tenure, Promotion, AnalysisRun, AnalysisIssue, Comparison, AdjustmentProposal, ProposalEvent, SourceDecision, IdCounter]
    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    manifest = {"seed":SEED,"scale":args.scale,"employees":count,"as_of":AS_OF.isoformat(),"tables":{},"source":"fully synthetic; no external personal data"}
    with Session(engine) as db:
        for model in table_order:
            rows = db.query(model).order_by(model.id).all()
            columns = [c.name for c in model.__table__.columns]
            path = inputs / f"{model.__tablename__}.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow([getattr(row,c).isoformat() if isinstance(getattr(row,c), (date,datetime)) else getattr(row,c) for c in columns])
            manifest["tables"][model.__tablename__] = {"rows":len(rows),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
            json_path = inputs / f"{model.__tablename__}.json"
            with json_path.open("w", encoding="utf-8") as handle:
                handle.write("[\n")
                for index, row in enumerate(rows):
                    obj = {c: getattr(row,c).isoformat() if isinstance(getattr(row,c),(date,datetime)) else str(getattr(row,c)) if isinstance(getattr(row,c),Decimal) else getattr(row,c) for c in columns}
                    handle.write((",\n" if index else "") + json.dumps(obj,ensure_ascii=False))
                handle.write("\n]\n")
    with (output / "schema.sql").open("w", encoding="utf-8") as handle:
        for model in table_order:
            handle.write(str(CreateTable(model.__table__).compile(dialect=postgresql.dialect())) + ";\n\n")
    with (output / "seed.sql").open("w", encoding="utf-8") as handle:
        handle.write("BEGIN;\n")
        for model in table_order:
            path = inputs / f"{model.__tablename__}.csv"
            with path.open(newline="", encoding="utf-8") as source_file:
                reader = csv.DictReader(source_file)
                columns = reader.fieldnames
                for row in reader:
                    values = ["NULL" if row[c] == "" else "'" + row[c].replace("'", "''") + "'" for c in columns]
                    handle.write(f"INSERT INTO {model.__tablename__} ({', '.join(columns)}) VALUES ({', '.join(values)});\n")
        handle.write("COMMIT;\n")
    (output / "ground_truth.json").write_text(json.dumps(sorted(truth,key=lambda x:x["target_id"]),indent=2),encoding="utf-8")
    with (output / "ground_truth.csv").open("w",newline="",encoding="utf-8") as handle:
        writer = csv.DictWriter(handle,fieldnames=["target_id","issue_type","expected_decision","reason"])
        writer.writeheader(); writer.writerows(sorted(truth,key=lambda x:x["target_id"]))
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    from validation import validate, checksums
    with Session(engine) as db:
        summary = validate(db)
    (output / "validation_summary.json").write_text(json.dumps(summary,indent=2,default=str),encoding="utf-8")
    (output / "checksums.json").write_text(json.dumps(checksums(output),indent=2),encoding="utf-8")
    if summary["error_count"]:
        raise SystemExit(f"Validation failed with {summary['error_count']} errors; see validation_summary.json")
    print(json.dumps({"database":args.database_url,"output":str(output),"employees":count,"salary_rows":len(salary),"truth_rows":len(truth)},indent=2))

if __name__ == "__main__":
    main()
