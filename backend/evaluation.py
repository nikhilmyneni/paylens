"""Offline scoring only. Detection must never import this module or its labels."""
import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from db import Base, normalize_database_url
from models import AnalysisRun, Comparison, Employee
from analysis import source_checksum

NON_FINDINGS = {"reviewed_no_action", "insufficient_comparators"}
LIMITATIONS = [
    "Measures recovery of synthetic injections, not real-world fairness or legal accuracy.",
    "Unlabelled flags count as false positives against injection labels; they may still warrant review.",
    "Employees without comparisons remain in the evaluation population; coverage is reported separately.",
]


def metrics(tp, fp, fn, tn=None):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    result = {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
              "recall": recall, "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None}
    if tn is not None:
        result["tn"] = tn
    return result


def score(population, predictions, truth):
    """Score employee-level detection and exact issue classification separately."""
    population = set(population)
    if len({row["target_id"] for row in truth}) != len(truth):
        raise ValueError("Duplicate truth targets are not supported by the single-outcome detector")
    labels = {row["target_id"]: row["issue_type"] for row in truth}
    if not set(labels).issubset(population) or not set(predictions).issubset(population):
        raise ValueError("Labels and predictions must reference the evaluation population")
    detected = {employee for employee, outcome in predictions.items() if outcome not in NON_FINDINGS}
    labelled = set(labels)
    by_issue = []
    for issue in sorted(set(labels.values()) | {predictions[e] for e in detected}):
        expected = {employee for employee, label in labels.items() if label == issue}
        actual = {employee for employee in detected if predictions[employee] == issue}
        by_issue.append({"issue_type": issue, "support": len(expected),
                         **metrics(len(expected & actual), len(actual - expected), len(expected - actual))})
    return {
        "population": len(population), "labelled_cases": len(labels),
        "metrics": metrics(len(detected & labelled), len(detected - labelled),
                           len(labelled - detected), len(population - detected - labelled)),
        "by_issue": by_issue,
        "missed_cases": [{"employee_id": e, "expected": labels[e], "actual": predictions.get(e, "not_compared")}
                         for e in sorted(labels) if predictions.get(e) != labels[e]],
        "extra_flags": [{"employee_id": e, "actual": predictions[e]} for e in sorted(detected - labelled)],
    }


def verify_sources(db, root, manifest):
    """Require the same source records, not merely the same employee count."""
    names = ("employee", "employee_assignment", "compensation_band", "fx_rate",
             "salary_record", "performance_evidence", "source_decision")
    for name in names:
        table = Base.metadata.tables[name]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow([column.name for column in table.columns])
        for row in db.execute(select(table).order_by(table.c.id)):
            writer.writerow([v.isoformat() if isinstance(v, (date, datetime)) else v for v in row])
        actual = hashlib.sha256(output.getvalue().encode("utf-8")).hexdigest()
        if actual != manifest.get("tables", {}).get(name, {}).get("sha256"):
            raise ValueError(f"The current {name} records differ from the labelled export. Evaluate a matching snapshot.")


def evaluate(db, run, directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest["as_of"] != run.as_of.isoformat():
        raise ValueError("Ground-truth date does not match the selected analysis run")
    if run.input_checksum and run.input_checksum != source_checksum(run.as_of, db):
        raise ValueError("The analysis snapshot is stale. Run analysis again before evaluating changed inputs.")
    verify_sources(db, root, manifest)
    truth = json.loads((root / "ground_truth.json").read_text(encoding="utf-8"))
    population = db.scalars(select(Employee.id)).all()
    predictions = dict(db.execute(select(Comparison.employee_id, Comparison.outcome).where(Comparison.run_id == run.id)).all())
    return {"available": True, "run_id": run.id, "as_of": run.as_of.isoformat(),
            "basis": "synthetic_injection_labels", **score(population, predictions, truth), "limitations": LIMITATIONS}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--output")
    args = parser.parse_args()
    with Session(create_engine(normalize_database_url(args.database_url))) as session:
        run = session.get(AnalysisRun, args.run_id) if args.run_id else session.scalar(
            select(AnalysisRun).order_by(AnalysisRun.as_of.desc(), AnalysisRun.created_at.desc()))
        if run is None:
            parser.error("No analysis run exists")
        result = evaluate(session, run, args.data_dir)
    rendered = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered)
