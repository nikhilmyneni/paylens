from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import DeclarativeBase

# Frozen schema for revision 0001. Never import live application models here.
class Base(DeclarativeBase):
    pass

def now():
    return datetime.now(timezone.utc)

class Role(Base):
    __tablename__ = "role"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    family: Mapped[str] = mapped_column(String(40))

class Level(Base):
    __tablename__ = "level"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    rank: Mapped[int] = mapped_column(Integer, unique=True)

class Location(Base):
    __tablename__ = "location"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3))

class Employee(Base):
    __tablename__ = "employee"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    hire_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")

class Assignment(Base):
    __tablename__ = "employee_assignment"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("role.id"))
    level_id: Mapped[str] = mapped_column(ForeignKey("level.id"))
    location_id: Mapped[str] = mapped_column(ForeignKey("location.id"))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    fte: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    __table_args__ = (CheckConstraint("fte > 0 AND fte <= 1"),)

class Band(Base):
    __tablename__ = "compensation_band"
    id: Mapped[str] = mapped_column(String(90), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("role.id"))
    level_id: Mapped[str] = mapped_column(ForeignKey("level.id"))
    location_id: Mapped[str] = mapped_column(ForeignKey("location.id"))
    currency: Mapped[str] = mapped_column(String(3))
    minimum: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    midpoint: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    maximum: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("role_id", "level_id", "location_id", "effective_from"), CheckConstraint("minimum <= midpoint AND midpoint <= maximum"))

class FxRate(Base):
    __tablename__ = "fx_rate"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    usd_per_unit: Mapped[Decimal] = mapped_column(Numeric(16, 8))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date] = mapped_column(Date)
    __table_args__ = (UniqueConstraint("currency", "effective_from"), CheckConstraint("usd_per_unit > 0"))

class SalaryRecord(Base):
    __tablename__ = "salary_record"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    effective_month: Mapped[date] = mapped_column(Date, index=True)
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    event_kind: Mapped[str] = mapped_column(String(20), default="baseline")
    __table_args__ = (CheckConstraint("monthly_amount > 0"), UniqueConstraint("employee_id", "effective_month", "event_kind"))

class PerformanceEvidence(Base):
    __tablename__ = "performance_evidence"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    period_end: Mapped[date] = mapped_column(Date)
    rating: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(String(150))
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5"),)

class Tenure(Base):
    __tablename__ = "tenure"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date)
    months_in_company: Mapped[int] = mapped_column(Integer)
    months_in_level: Mapped[int] = mapped_column(Integer)

class Promotion(Base):
    __tablename__ = "promotion"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    from_assignment_id: Mapped[str] = mapped_column(ForeignKey("employee_assignment.id"))
    to_assignment_id: Mapped[str] = mapped_column(ForeignKey("employee_assignment.id"))
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(100))

class AnalysisRun(Base):
    __tablename__ = "analysis_run"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    as_of: Mapped[date] = mapped_column(Date)
    ruleset: Mapped[str] = mapped_column(String(30))
    input_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AnalysisIssue(Base):
    __tablename__ = "analysis_issue"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_run.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    issue_type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)

class IdCounter(Base):
    __tablename__ = "id_counter"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    value: Mapped[int] = mapped_column(Integer)

class Comparison(Base):
    __tablename__ = "comparison_result"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("analysis_run.id"), index=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"), index=True)
    salary_id: Mapped[str] = mapped_column(ForeignKey("salary_record.id"))
    band_id: Mapped[str | None] = mapped_column(ForeignKey("compensation_band.id"), nullable=True)
    group_key: Mapped[str] = mapped_column(String(80))
    peer_count: Mapped[int] = mapped_column(Integer)
    annual_fte: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    compa_ratio: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    band_position: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    expected_annual: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    residual_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    outcome: Mapped[str] = mapped_column(String(40), index=True)
    explanation: Mapped[str] = mapped_column(Text)

class AdjustmentProposal(Base):
    __tablename__ = "adjustment_proposal"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparison_result.id"))
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"))
    proposed_annual: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    rationale: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(20), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ProposalEvent(Base):
    __tablename__ = "proposal_event"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey("adjustment_proposal.id"), index=True)
    prior_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_state: Mapped[str] = mapped_column(String(20))
    actor: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class SourceDecision(Base):
    __tablename__ = "source_decision"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(ForeignKey("employee.id"))
    salary_id: Mapped[str] = mapped_column(ForeignKey("salary_record.id"))
    reported_band_id: Mapped[str | None] = mapped_column(ForeignKey("compensation_band.id"), nullable=True)
    reported_fte: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    reported_fx: Mapped[Decimal | None] = mapped_column(Numeric(16, 8), nullable=True)
    reported_group_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    applied_proposal_id: Mapped[str | None] = mapped_column(ForeignKey("adjustment_proposal.id"), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AuditEvent(Base):
    __tablename__ = "audit_event"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    subject_id: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
