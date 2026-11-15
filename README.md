# PayLens

PayLens turns a compensation discrepancy into a reviewable decision. It compares salary histories with effective-dated role, level and location bands, accounts for working hours and currency, and shows the documented factors behind each finding. Reviewers can inspect evidence, propose an annual salary, approve or reject the change, and trace an applied adjustment back to its source records.

Built for the YottaFlex compensation-disparity hackathon using synthetic employees only.

**Verification:** 29 backend tests and 10 subtests pass locally; the PostgreSQL integration checks also pass in GitHub CI. The frontend production build and desktop/mobile browser checks pass. [Test coverage and commands](docs/testing.md).

**Recorded full-scale evaluation:** 5,000 employees, 200 role/level combinations and 180,000 monthly salary records. The synthetic baseline yielded 81 true positives, 31 false positives and no false negatives: 72.32% precision, 100% recall and 83.94% F1. These are labelled-scenario results, not evidence of real-world fairness. [Evaluation details](docs/evaluation.md).

**Live demo:** [paylens-olive.vercel.app](https://paylens-olive.vercel.app)  [API documentation](https://paylens-api.vercel.app/docs)

The React frontend and FastAPI API deploy independently on Vercel; a dedicated Supabase PostgreSQL project persists the synthetic records and review history.

## Start a review

1. Open **Inbox** to inspect a pay gap, or **Issues** for a data exception.
2. Read the employee's actual and expected pay, peer count, band position and supporting history.
3. Propose an adjustment using the compensation slider or an exact annual amount, and record a reason.
4. Submit the draft for a manager decision. HR can apply an approved adjustment; the application appends a salary event and approval history.
5. Open **Results** for detection metrics or **Quality** for integrity checks, comparison coverage and dataset counts.

The interface includes responsive layouts, loading skeletons, keyboard controls and system-aware light/dark themes. It displays saved analyses; it does not claim a live payroll feed.

## Run locally

Requires Python 3.13 and Node.js 22. SQLite supports a local demo without hosted accounts. From the repository root:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python bootstrap.py --seed --output ../data/generated/starter
uvicorn main:app --reload
```

In a second terminal:

```powershell
cd frontend
npm ci
$env:VITE_API_BASE_URL = "http://localhost:8000"
npm run dev
```

Open `http://localhost:5173`; API documentation is at `http://localhost:8000/docs`. The bootstrap migrates the database and seeds it only when empty. Existing review history is preserved. Evaluation reads the matching `data/generated/starter` exports by default; set `EVALUATION_DATA_DIR` for a different dataset.

For the three-container PostgreSQL setup, install and start Docker Desktop, then run:

```powershell
.\scripts\start-three-tier.ps1
```

Open `http://localhost:8080`. Nginx routes API requests to the private backend; only the frontend port is published. See [Compose setup](docs/three-tier.md) for health checks and stopping without deleting data.

## Three-tier design

| Tier | Stack | Owns |
| --- | --- | --- |
| Presentation | React, TypeScript, Vite | Review queue, evidence, proposal form, quality and evaluation views |
| Application | FastAPI, SQLAlchemy, Alembic | Analysis rules, role checks, proposal transitions, validation and API |
| Persistence | PostgreSQL; SQLite for local development | Master records, effective-dated histories, comparison snapshots and audit events |

The browser calls the API; database credentials stay on the backend. Cloud targets are two independent Vercel projects and a dedicated Supabase PostgreSQL project. [Architecture](ARCHITECTURE.md) ? [Deployment guide](docs/vercel.md).

## Data, exceptions and outputs

One generator produces starter and full datasets with fixed seed `20261022`. Parent records precede dependent salary, assignment, promotion and evidence records. Three years of salary histories include part-time changes, currency changes and promotions. Labels follow documented scenarios and are exported separately from detector inputs.

Required exceptions cover expired bands, ignored FTE, missing currency conversion, adjustments without approval and unjustified comparison groups. The suite also exercises missing source records, date boundaries, invalid amounts, duplicate applications and concurrent decisions.

Generate the full dataset against a fresh local database:

```powershell
python backend/generate.py --scale full --database-url sqlite:///./compensation-full.db --output data/generated/full
python backend/validation.py --database-url sqlite:///./compensation-full.db
python backend/evaluation.py --database-url sqlite:///./compensation-full.db --data-dir data/generated/full --output data/generated/full-evaluation.json
```

Exports include CSV/JSON tables, SQL seed data, separate ground truth, source manifest, validation summary and checksums. Generated source datasets and databases are excluded from Git; the generator recreates them. Two small evaluation files (manifest and separate labels) are bundled for the hosted synthetic snapshot; they are never detector inputs. [Reproducibility procedure](docs/testing.md#generated-data-validation-and-reproducibility).

## Tests and reviewer guide

```powershell
python -m pip install pytest httpx
python -m pytest backend/tests -q
cd frontend
npm ci
npm run build
```

Install backend requirements first, in the same Python environment. CI runs backend tests, PostgreSQL generation and migration guards, fixed-seed export comparison and the TypeScript/Vite build. Browser checks are documented separately and require a running API and frontend.

| Material | What to inspect |
| --- | --- |
| [Edge cases and validation](docs/testing.md) | Scenario-to-test mapping and reproducible commands |
| [Data dictionary](docs/data_dictionary.md) | Fields, types, relationships and validation rules |
| [Evaluation](docs/evaluation.md) | Metric definitions, ground-truth separation and measured results |
| [Current build](docs/current-build.md) | Verified behavior and remaining scope |
| [Database upgrades](docs/database-upgrades.md) | Migrations and append-only history protection |
| [Browser checks](frontend/tests/README.md) | Layout, loading, themes, content and slider tests |

## Scope and limitations

Expected pay uses deterministic documented factors rather than fitted regression. Comparable groups use role/level/location keys. Approval is one manager decision followed by HR application. Historical source decisions are not a complete point-in-time event replay.

Demo actors and role tokens are not production identity or employee-level authorization. Use synthetic records for this prototype; a real compensation deployment needs SSO, scoped access and operational controls. Missing evaluation artifacts produce an unavailable report instead of invented scores.

Built with Codex assistance for implementation, UI iteration and verification. The repository retains source, tests, migrations, manifests, documentation and required logo/font assets. Screenshots, unused design styles, installed modules, local databases, generated exports and credentials are excluded. The bundled DM Sans font includes its license.
