# Edge cases and validation

Tests live in `backend/tests/` and `frontend/tests/`. Fixtures are constructed by the tests; downloaded or committed employee datasets are not required.

## Backend coverage

| Scenario | Expected behavior | Test module |
| --- | --- | --- |
| Expired band reference | Report `expired_band_used` | `test_analysis.py` |
| Part-time FTE ignored | Report `fte_ignored`; normalize actual pay | `test_analysis.py` |
| Missing currency conversion | Report missing conversion rather than assume a rate | `test_analysis.py` |
| Unapproved adjustment | Detect imported anomaly; reject live application | `test_analysis.py`, `test_api_workflow.py` |
| Incomparable roles grouped | Report invalid comparison group | `test_analysis.py` |
| Missing or overlapping effective dates | Reject ambiguous references; adjacent non-overlapping dates pass | `test_analysis.py`, `test_validation.py` |
| Missing salary or assignment | Persist explicit coverage issues | `test_analysis.py` |
| Broken FK, reversed dates, invalid band, zero FTE, negative FX | Report validation failures | `test_validation.py` |
| Approval skipped, rejected draft applied | Reject transition and preserve history | `test_validation.py`, `test_api_workflow.py` |
| Stale version / concurrent decisions / repeat application | Reject stale changes and avoid duplicate salary events | `test_api_workflow.py` |
| Future FTE or role change | Use effective FTE; require another review for a new role | `test_api_workflow.py` |
| Invalid effective adjustment date | Reject same/past date and non-month-start date | `test_api_workflow.py` |
| Unauthorized role / missing token | Deny protected actions | `test_api_workflow.py`, `test_reporting.py` |
| Update/delete historical events | Database guards reject mutation | `test_migrations.py` |
| Existing database upgrade | Preserve records | `test_migrations.py` |
| Wrong classification, missing labels, zero denominator | Report misses, unavailable labels or null metrics | `test_reporting.py` |
| Ground truth leakage | AST guard prevents detector imports/label reads | `test_reporting.py` |

Run from the repository root after installing backend dependencies:

```powershell
python -m pip install pytest httpx
python -m pytest backend/tests -q
```

The latest local run passed 28 tests and 10 subtests; one PostgreSQL-specific test skipped because PostgreSQL was not available locally. CI runs the PostgreSQL guard test against its service database. Local success alone does not establish deployed PostgreSQL behavior.

## Generated data validation and reproducibility

```powershell
python backend/generate.py --scale starter --database-url sqlite:///./validation-a.db --output data/generated/a
python backend/generate.py --scale starter --database-url sqlite:///./validation-b.db --output data/generated/b
python backend/validation.py --database-url sqlite:///./validation-a.db
python backend/validation.py --compare data/generated/a data/generated/b
```

Use fresh database files for generation. Both runs use the default seed `20261022`. `validation.py` validates joins, duplicate keys/events, dates, enums, amounts and workflow consistency; exported summaries and checksums are generated locally. Use `--scale full` for 5,000 employees and three years of salary history. Labels remain in separate ground-truth files and are only read by evaluation.

## Browser coverage

See [browser checks](../frontend/tests/README.md): responsive layouts, scrolling, skeletons, error recovery, system/manual themes, content claims, missing bands/currencies, percentage formatting and compensation slider interactions. The slider test intercepts writes.

## Continuous integration

`.github/workflows/ci.yml` runs backend tests, PostgreSQL generation/migration checks, two-run reproducibility and the TypeScript/Vite production build. Browser checks are run separately against a running local frontend and API.
