# Version 1 evaluation

## Runnable evaluation and reports

The evaluator now runs independently of detection:

```powershell
cd backend
python evaluation.py --database-url sqlite:///./compensation.db --data-dir ../data/generated/starter --output ../data/generated/evaluation.json
```

Use the export directory that belongs to the selected database. The evaluator checks source-table hashes, the analysis date, and (for new runs) the analysis input checksum. A mismatched snapshot is rejected rather than scored against unrelated labels. The optional `--run-id` selects an archived run when its inputs are available.

`GET /api/v1/evaluation` exposes aggregate and per-issue precision/recall/F1, exact-classification misses, and extra flags. Configure `EVALUATION_DATA_DIR` to point to the matching exports; an unavailable or changed dataset produces `available: false`, not fabricated zero scores. `GET /api/v1/quality` exposes current integrity checks and comparison coverage. Both routes require a manager, HR, or admin role.

Binary detection counts an employee flagged for any issue as detected; per-issue scores additionally require the correct issue. Undefined precision or recall is `null`. Employees with missing inputs remain in the population and are also exposed in the quality report. Labels never enter the detector's inputs.

The upgraded starter generator was run twice: all 40 exported artifacts matched. Its 240 employees and 11 injected cases yielded TP11 / FP0 / FN0 / TN229. This small starter fixture is not evidence of perfect real-world performance. The larger original full-run results below remain a separate recorded baseline.

Analysis `as_of` currently selects salary and performance history. Source decisions are review evidence and may have been recorded later; it is not a complete point-in-time event replay.

## Recorded full-scale baseline

The fixed-seed full run contains 5,000 employees, 200 role/level combinations, 1,800 effective-dated bands across three locations and years, and 180,000 monthly salary records. The 81 sealed ground-truth cases include 76 unexplained-pay injections and the five required source/workflow exceptions. Dataset validation found zero integrity errors.

Against the separate ground truth for the 2026-12 analysis run:

| Measure | Result |
| --- | ---: |
| True positives | 81 |
| False positives | 31 |
| False negatives | 0 |
| True negatives | 4,888 |
| Precision | 72.32% |
| Recall | 100% |
| F1 | 83.94% |

All 81 labelled cases matched their exact `issue_type`. The 31 additional findings are low-pay records caused by normal synthetic variation that crossed the review threshold; they are counted as false positives against the injection labels. A flag calls for human review, so the system does not auto-adjust compensation. These numbers describe this synthetic dataset and should not be treated as real-world fairness or legal accuracy.

The generator was run twice at full scale with seed `20261022`. All 36 exported artifacts had matching SHA-256 hashes. See [reproducibility.md](reproducibility.md).
