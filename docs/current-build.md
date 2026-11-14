# Current build verification

## Implemented in this revision

- Independent evaluation module and protected evaluation/data-quality endpoints.
- Evaluation checks source-export hashes, run date and new-run input fingerprints before scoring.
- Atomic proposal state/version updates, sequential proposal IDs, configurable adjustment dates and effective assignment checks.
- Source-input fingerprints create new analysis snapshots after changes. Missing salary/assignment inputs produce explicit analysis issues.
- Alembic upgrades preserve existing prototype data. Database triggers protect salary, proposal-event and audit history from updates/deletes.
- Compose initialization migrates and seeds only an empty database. Subsequent starts preserve records.
- Locked frontend dependencies and `npm ci` for reproducible installation.
- Fresh review workspace, report views, skeleton states and responsive layouts.
- System-default light/dark themes, persistent manual preferences and a circular theme reveal with reduced-motion fallback.
- UI content audit removed unsupported live/sealed claims and corrected exception evidence, saved-run labels, category counts and coverage percentage formatting.

## Verified locally

- Backend: 30 tests run, 29 passed; the PostgreSQL-only guard test skipped because no PostgreSQL server is available.
- Updated starter generator: two runs, all 40 exported artifacts identical.
- Runnable evaluator against full baseline: 5,000 employees, TP81 / FP31 / FN0 / TN4888; precision 72.32%, recall 100%, F1 83.94%.
- Local starter evaluation: 240 employees, TP11 / FP0 / FN0 / TN229.
- Browser: desktop/tablet/phone queue scrolling and report rendering checked. Complete proposal workflow verified against an isolated database copy: four approval-history events and one applied salary record.
- Legacy SQLite upgrade preserves data; append-only triggers reject mutations; repeated bootstrap preserves existing data.

## Remaining scope

GitHub CI passes PostgreSQL generation and append-only migration guards. The public Vercel frontend/API connect to a dedicated Supabase PostgreSQL project with 5,000 employees and 180,000 salary records. Hosted readiness, full comparison coverage, validation and evaluation have been verified. Docker remains unverified locally because no Docker engine was available.

The app still uses documented deterministic factors rather than a fitted statistical model. Comparable groups are role/level/location keys, not user-managed many-to-many memberships. Approval remains one manager decision followed by HR application. Authentication is a demo/role-token implementation, without employee ownership or manager-team authorization. Layered service/repository extraction, generated API types and full lint/type tooling remain future work.

Analysis dates select salary/performance history; later recorded source decisions may still be considered as review evidence. This is not a complete point-in-time event replay. Synthetic injection labels measure known test cases, not real-world fairness.

## Deployment checks

The first PostgreSQL CI run exposed a parent-insertion ordering bug in the generator. The fix flushes masters before bands, employees before their histories and assignments before promotions. SQLite generation now enables foreign-key enforcement; a regression test exercises the actual generator. The corrected PostgreSQL CI run passes.

The dedicated Supabase tables have RLS enabled and direct access revoked from anon/authenticated roles. Anonymous employee reads were verified denied. FastAPI connects using server-side credentials; the public app remains a synthetic demo with demo-role authorization.

Hosted browser checks passed at 1440px, 768px and 390px: queue scrolling, report loading and no horizontal overflow or JavaScript errors. Slider checks passed in light desktop and dark mobile themes, including intercepted exact-value submission. Hosted persistence was verified using ADJ-2026-000002 (EMP-000001): draft, submitted, then rejected, with three persisted events and no salary change. This labelled verification record remains in the append-only history.
