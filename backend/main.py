import os
import json
import hmac
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from analysis import active, compute
from db import SessionLocal, engine, initialize_database
from models import (AdjustmentProposal, AnalysisIssue, AnalysisRun, Assignment, AuditEvent, Band, IdCounter,
                    Comparison, Employee, PerformanceEvidence, ProposalEvent, Role,
                    SalaryRecord, SourceDecision)

app = FastAPI(title="PayLens API", version="1.0.0")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST"], allow_headers=["*"])
initialize_database(engine)

def get_db():
    with SessionLocal() as db:
        yield db

def actor(x_actor: str = Header(default="demo-hr"), x_role: str = Header(default="hr"), x_api_key: str = Header(default="")):
    if os.getenv("DEMO_MODE", "true").lower() != "true":
        tokens = json.loads(os.getenv("ROLE_TOKENS", "{}"))
        expected = tokens.get(x_role)
        if not expected or not hmac.compare_digest(x_api_key, expected):
            raise HTTPException(401, "Authentication required")
    if x_role not in {"employee", "manager", "hr", "it_ops", "admin"}:
        raise HTTPException(403, "Unknown role")
    return {"name": x_actor, "role": x_role}

def require(user, allowed):
    if user["role"] not in allowed:
        raise HTTPException(403, "Role is not permitted")

def latest_run(db):
    run = db.scalar(select(AnalysisRun).order_by(AnalysisRun.as_of.desc(), AnalysisRun.created_at.desc()))
    if not run:
        raise HTTPException(409, "No analysis run. Run POST /api/v1/analysis-runs first.")
    return run

def dec(value):
    return float(value) if value is not None else None

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}

@app.get("/api/v1/summary")
def summary(db: Session = Depends(get_db), user=Depends(actor)):
    require(user, {"manager", "hr", "admin"})
    run = latest_run(db)
    counts = dict(db.execute(select(Comparison.outcome, func.count()).where(Comparison.run_id == run.id).group_by(Comparison.outcome)).all())
    coverage_issues = db.scalar(select(func.count()).select_from(AnalysisIssue).where(AnalysisIssue.run_id == run.id))
    exceptions = sum(counts.get(k, 0) for k in ["missing_effective_band", "expired_band_used", "fte_ignored", "missing_fx", "incomparable_group", "unapproved_adjustment", "missing_fx_rate", "invalid_band", "incorrect_fx"]) + coverage_issues
    flagged = counts.get("unexplained_gap",0) + counts.get("pay_outside_band",0)
    return {"run_id":run.id,"as_of":run.as_of,"input_checksum":run.input_checksum,"total_employees":db.scalar(select(func.count()).select_from(Employee)),"assessed_employees":sum(counts.values()),"coverage_issues":coverage_issues,"flagged":flagged,"exceptions":exceptions,"proposals":db.scalar(select(func.count()).select_from(AdjustmentProposal)),"by_outcome":counts}

@app.get("/api/v1/comparisons")
def comparisons(outcome: str | None = None, q: str | None = None, limit: int = Query(30, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user=Depends(actor)):
    require(user, {"manager", "hr", "admin"})
    run = latest_run(db)
    query = select(Comparison, Employee).join(Employee, Comparison.employee_id == Employee.id).where(Comparison.run_id == run.id)
    if outcome == "exception":
        query = query.where(Comparison.outcome.in_(["missing_effective_band", "expired_band_used", "fte_ignored", "missing_fx", "incomparable_group", "unapproved_adjustment", "missing_fx_rate", "invalid_band", "incorrect_fx"]))
    elif outcome:
        query = query.where(Comparison.outcome == outcome)
    if q: query = query.where((Employee.id.ilike(f"%{q}%")) | (Employee.display_name.ilike(f"%{q}%")))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(query.order_by(Comparison.outcome, Employee.id).limit(limit).offset(offset)).all()
    band_ids = [r.band_id for r,_ in rows if r.band_id]
    band_map = {b.id:b for b in db.scalars(select(Band).where(Band.id.in_(band_ids))).all()}
    role_map = {r.id:r.name for r in db.scalars(select(Role)).all()}
    items = []
    for result, person in rows:
        role_id, level_id, location_id = result.group_key.split("|")
        band = band_map.get(result.band_id)
        items.append({"id":result.id,"employee_id":person.id,"display_name":person.display_name,"role":role_map.get(role_id, role_id),"level":level_id,"location":location_id,"annual_fte":dec(result.annual_fte),"currency":band.currency if band else None,"band_id":result.band_id,"salary_id":result.salary_id,"compa_ratio":dec(result.compa_ratio),"band_position":dec(result.band_position),"expected_annual":dec(result.expected_annual),"residual_pct":dec(result.residual_pct),"peer_count":result.peer_count,"outcome":result.outcome,"explanation":result.explanation})
    return {"items":items,"total":total,"limit":limit,"offset":offset}

@app.get("/api/v1/employees/{employee_id}/timeline")
def timeline(employee_id: str, db: Session = Depends(get_db), user=Depends(actor)):
    require(user, {"manager", "hr", "admin"})
    person = db.get(Employee, employee_id)
    if not person: raise HTTPException(404, "Employee not found")
    run = latest_run(db)
    comps = db.scalars(select(Comparison).where(Comparison.employee_id == employee_id, Comparison.run_id == run.id)).all()
    salaries = db.scalars(select(SalaryRecord).where(SalaryRecord.employee_id == employee_id).order_by(SalaryRecord.effective_month.desc()).limit(36)).all()
    assigns = db.scalars(select(Assignment).where(Assignment.employee_id == employee_id).order_by(Assignment.effective_from)).all()
    proposals = db.scalars(select(AdjustmentProposal).where(AdjustmentProposal.employee_id == employee_id)).all()
    pids = [p.id for p in proposals]
    events = db.scalars(select(ProposalEvent).where(ProposalEvent.proposal_id.in_(pids)).order_by(ProposalEvent.occurred_at)).all() if pids else []
    return {"employee":{"id":person.id,"display_name":person.display_name,"hire_date":person.hire_date,"status":person.status},"comparisons":[{"id":c.id,"outcome":c.outcome,"annual_fte":dec(c.annual_fte),"expected_annual":dec(c.expected_annual),"compa_ratio":dec(c.compa_ratio),"explanation":c.explanation,"group_key":c.group_key,"peer_count":c.peer_count} for c in comps],"salaries":[{"id":s.id,"effective_month":s.effective_month,"monthly_amount":dec(s.monthly_amount),"currency":s.currency,"event_kind":s.event_kind} for s in salaries],"assignments":[{"id":a.id,"role_id":a.role_id,"level_id":a.level_id,"location_id":a.location_id,"fte":dec(a.fte),"effective_from":a.effective_from,"effective_to":a.effective_to} for a in assigns],"proposals":[{"id":p.id,"state":p.state,"proposed_annual":dec(p.proposed_annual),"currency":p.currency,"rationale":p.rationale,"version":p.version} for p in proposals],"events":[{"id":e.id,"proposal_id":e.proposal_id,"prior_state":e.prior_state,"next_state":e.next_state,"actor":e.actor,"reason":e.reason,"occurred_at":e.occurred_at} for e in events]}

class RunRequest(BaseModel):
    as_of: date = date(2026, 12, 1)

@app.post("/api/v1/analysis-runs")
def create_run(payload: RunRequest, db: Session = Depends(get_db), user=Depends(actor)):
    require(user, {"hr", "admin"})
    run = compute(payload.as_of, db)
    return {"run_id":run.id,"as_of":run.as_of,"ruleset":run.ruleset,"input_checksum":run.input_checksum}

class ProposalCreate(BaseModel):
    comparison_id: str
    proposed_annual: Decimal = Field(gt=0)
    rationale: str = Field(min_length=10)

def event(db, proposal, next_state, user, reason):
    prior = proposal.state
    changed = db.execute(update(AdjustmentProposal).where(
        AdjustmentProposal.id == proposal.id,
        AdjustmentProposal.version == proposal.version,
        AdjustmentProposal.state == prior,
    ).values(state=next_state, version=AdjustmentProposal.version + 1).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Proposal changed; refresh and retry")
    db.refresh(proposal)
    db.add(ProposalEvent(id=f"PEV-{uuid4().hex[:24]}", proposal_id=proposal.id, prior_state=prior, next_state=next_state, actor=user["name"], reason=reason, occurred_at=datetime.now(timezone.utc)))
    db.add(AuditEvent(id=f"AUD-{uuid4().hex[:24]}", actor=user["name"], action=f"proposal.{next_state}", subject_id=proposal.id, detail=reason))

def next_proposal_id(db, year):
    """Allocate under a database write lock, including IDs from imported seed data."""
    prefix = f"ADJ-{year}-"
    existing = db.scalars(select(AdjustmentProposal.id).where(AdjustmentProposal.id.like(prefix + "%"))).all()
    initial = max((int(value[len(prefix):]) for value in existing if value[len(prefix):].isdigit()), default=0)
    dialect = db.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise HTTPException(503, "Proposal allocation requires PostgreSQL or SQLite")
    counter_id = f"proposal-{year}"
    db.execute(insert(IdCounter).values(id=counter_id, value=initial).on_conflict_do_nothing(index_elements=[IdCounter.id]))
    value = db.scalar(update(IdCounter).where(IdCounter.id == counter_id).values(value=IdCounter.value + 1).returning(IdCounter.value))
    return f"{prefix}{value:06d}"

@app.post("/api/v1/proposals")
def create_proposal(payload: ProposalCreate, db: Session = Depends(get_db), user=Depends(actor)):
    require(user, {"hr", "admin"})
    result = db.get(Comparison, payload.comparison_id)
    if not result: raise HTTPException(404, "Comparison not found")
    band = db.get(Band, result.band_id) if result.band_id else None
    if not band: raise HTTPException(422, "A valid band is required")
    run = db.get(AnalysisRun, result.run_id)
    pid = next_proposal_id(db, run.as_of.year)
    proposal = AdjustmentProposal(id=pid, comparison_id=result.id, employee_id=result.employee_id, proposed_annual=payload.proposed_annual, currency=band.currency, rationale=payload.rationale, state="draft", version=1)
    db.add(proposal); db.flush()
    db.add(ProposalEvent(id=f"PEV-{uuid4().hex[:24]}", proposal_id=pid, prior_state=None, next_state="draft", actor=user["name"], reason=payload.rationale))
    db.commit()
    return {"id":pid,"state":proposal.state,"version":proposal.version}

class Transition(BaseModel):
    reason: str = Field(min_length=5)
    version: int = Field(ge=1)
    decision: str | None = None
    effective_date: date | None = None

def transition(pid, payload, next_state, allowed_from, roles, db, user):
    require(user, roles)
    proposal = db.get(AdjustmentProposal, pid)
    if not proposal: raise HTTPException(404, "Proposal not found")
    if proposal.version != payload.version: raise HTTPException(409, "Proposal changed; refresh and retry")
    if proposal.state not in allowed_from: raise HTTPException(409, f"Cannot transition {proposal.state} to {next_state}")
    event(db, proposal, next_state, user, payload.reason)
    db.commit()
    return {"id":pid,"state":proposal.state,"version":proposal.version}

@app.post("/api/v1/proposals/{pid}/submit")
def submit(pid: str, payload: Transition, db: Session = Depends(get_db), user=Depends(actor)):
    return transition(pid,payload,"submitted",{"draft"},{"hr","admin"},db,user)

@app.post("/api/v1/proposals/{pid}/decision")
def decide(pid: str, payload: Transition, db: Session = Depends(get_db), user=Depends(actor)):
    if payload.decision not in {"approved","rejected"}: raise HTTPException(422,"decision must be approved or rejected")
    return transition(pid,payload,payload.decision,{"submitted"},{"manager","admin"},db,user)

@app.post("/api/v1/proposals/{pid}/apply")
def apply(pid: str, payload: Transition, db: Session = Depends(get_db), user=Depends(actor)):
    require(user,{"hr","admin"})
    proposal = db.get(AdjustmentProposal,pid)
    if not proposal: raise HTTPException(404,"Proposal not found")
    if proposal.state != "approved":
        db.add(AuditEvent(id=f"AUD-{uuid4().hex[:24]}",actor=user["name"],action="proposal.apply_denied",subject_id=pid,detail="Proposal lacks approval")); db.commit()
        raise HTTPException(409,"Proposal must be approved before application")
    if proposal.version != payload.version: raise HTTPException(409,"Proposal changed; refresh and retry")
    comparison = db.get(Comparison, proposal.comparison_id)
    run = db.get(AnalysisRun, comparison.run_id)
    effective = payload.effective_date or date(run.as_of.year + (run.as_of.month == 12), run.as_of.month % 12 + 1, 1)
    if effective.day != 1 or effective <= run.as_of:
        raise HTTPException(422, "Effective date must be the first day of a month after the analysis date")
    assignments = db.scalars(select(Assignment).where(Assignment.employee_id == proposal.employee_id)).all()
    try:
        assignment = active(assignments, effective)
    except ValueError as exc:
        raise HTTPException(422, f"No unique assignment on the adjustment date: {exc}") from exc
    band = db.get(Band, comparison.band_id) if comparison.band_id else None
    if not band or (assignment.role_id, assignment.level_id, assignment.location_id) != (band.role_id, band.level_id, band.location_id):
        raise HTTPException(409, "Role, level or location changed; complete a new compensation review before applying")
    conflict = db.scalar(select(SalaryRecord).where(SalaryRecord.employee_id==proposal.employee_id,SalaryRecord.effective_month==effective,SalaryRecord.event_kind=="adjustment"))
    if conflict: raise HTTPException(409,"An adjustment already exists for this employee and month")
    annual_actual = proposal.proposed_annual * assignment.fte
    sid = f"SAL-{proposal.employee_id}-{effective:%Y-%m}-{pid}"
    # Reserve the transition before inserting salary; both commit or roll back together.
    event(db,proposal,"applied",user,payload.reason)
    db.add(SalaryRecord(id=sid,employee_id=proposal.employee_id,effective_month=effective,monthly_amount=(annual_actual/12).quantize(Decimal("0.01")),currency=proposal.currency,event_kind="adjustment"))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An adjustment already exists for this employee and month") from exc
    return {"id":pid,"state":proposal.state,"version":proposal.version,"salary_id":sid,"effective_date":effective}


from reporting import register_reports

register_reports(app, get_db, actor, require, latest_run)
