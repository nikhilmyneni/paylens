"""Read-only reporting routes, kept separate from the detection engine."""
import os
from pathlib import Path

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db import Base
from evaluation import LIMITATIONS, evaluate
from models import Comparison, Employee
from validation import validate


def register_reports(app, get_db, actor, require, latest_run):
    @app.get("/api/v1/evaluation")
    def evaluation_report(db: Session = Depends(get_db), user=Depends(actor)):
        require(user, {"manager", "hr", "admin"})
        run = latest_run(db)
        directory = os.getenv("EVALUATION_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "generated" / "starter"))
        try:
            return evaluate(db, run, directory)
        except (OSError, ValueError, KeyError) as exc:
            return {"available": False, "run_id": run.id, "as_of": run.as_of,
                    "reason": str(exc) if not isinstance(exc, OSError) else "Matching labelled export is not configured on this server.",
                    "limitations": LIMITATIONS}

    @app.get("/api/v1/quality")
    def quality_report(db: Session = Depends(get_db), user=Depends(actor)):
        require(user, {"manager", "hr", "admin"})
        run = latest_run(db)
        result = validate(db)
        total = db.scalar(select(func.count()).select_from(Employee))
        compared = db.scalar(select(func.count(func.distinct(Comparison.employee_id))).where(Comparison.run_id == run.id))
        issues = []
        table = Base.metadata.tables.get("analysis_issue")
        if table is not None:
            issues = [dict(row) for row in db.execute(select(table).where(table.c.run_id == run.id)).mappings()]
        categories = {
            "Keys and relationships": {"duplicate_primary_key", "orphan_foreign_key", "duplicate_salary_event"},
            "Effective dates": {"overlapping_effective_dates", "reverse_effective_dates"},
            "Amounts and factors": {"invalid_band_arithmetic", "invalid_fx_rate", "invalid_fte", "invalid_tenure", "invalid_rating"},
            "Event lifecycle": {"invalid_promotion_transition", "invalid_proposal_transition"},
        }
        checks = []
        for name, kinds in categories.items():
            count = sum(error["type"] in kinds for error in result["errors"])
            checks.append({"name": name, "status": "failed" if count else "passed", "count": count})
        checks.append({"name": "Analysis coverage", "status": "passed" if compared == total else "failed", "count": total - compared})
        return {"run_id": run.id, "as_of": run.as_of, "source": "synthetic", **result,
                "status": "attention" if result["error_count"] or compared != total else "passed",
                "coverage": {"employees": total, "compared": compared, "excluded": total - compared,
                             "percent": 100 * compared / total if total else 0},
                "analysis_issues": issues, "checks": checks}
