# Local three-tier deployment

The Compose deployment runs three independent long-lived services:

```text
Browser -> localhost:8080 -> nginx + React
                                |
                            /api/ proxy
                                |
                         FastAPI :8000
                                |
                         PostgreSQL :5432
```

Only nginx publishes a host port, bound to loopback. The frontend and API share the `app` network. PostgreSQL and the API share the internal `data` network; the frontend cannot reach PostgreSQL directly. No database password is embedded in the frontend. The browser uses relative API URLs so no cross-origin setup is needed for this local deployment.

## Start

Install and start Docker Desktop with its Linux/WSL 2 backend. From the repository root:

```powershell
.\scripts\start-three-tier.ps1
```

The script checks Docker and Compose before changing files. If `.env` is absent, it creates one with a cryptographically random URL-safe password. It never replaces an existing `.env`. For manual setup, copy `.env.example` and supply a non-empty URL-safe password, then run `docker compose up --build -d`.

The one-shot `initialize` service waits for PostgreSQL, applies migrations and seeds a completely empty database. It preserves existing employees and review events on subsequent starts. The API starts after initialization succeeds; nginx starts after the API's database-backed readiness check passes. The `pgdata` and `seeddata` volumes persist database records and evaluation exports.

Open **http://localhost:8080**. Existing Vite/FastAPI preview processes on ports 5173 and 8000 are unaffected. The Compose backend and database do not expose host ports.

## Check and stop

```powershell
.\scripts\check-three-tier.ps1
docker compose ps
docker compose logs initialize backend frontend
docker compose down
```

The check script verifies nginx, the proxied database readiness endpoint, seeded employee counts and a reviewable comparison. `docker compose down` preserves volumes. Do not use `down --volumes` when retaining review history.

The frontend build uses the committed npm lockfile. Nginx proxies `/api/v1/*` unchanged to FastAPI; `/api/ready` maps to the backend `/ready` endpoint. The container build fixes the frontend API base to `/` independently of Vite development settings.

## Verification status

The files and PowerShell scripts can be validated without Docker, but successful container execution requires a running Docker engine. Docker was not available on this workstation when these deployment files were prepared, so a completed three-container run is not yet claimed. Local SQLite preview checks are separate from PostgreSQL deployment verification.

This is a loopback-only synthetic demonstration. A public deployment additionally needs HTTPS, domain routing and appropriate authentication; do not expose demo actors with real compensation records.
