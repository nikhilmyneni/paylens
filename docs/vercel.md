# Deployed three-tier setup

- Frontend: https://paylens-olive.vercel.app (`paylens`, Vite, repository root `frontend/`).
- API: https://paylens-api.vercel.app (`paylens-api`, FastAPI, repository root `backend/`, Mumbai `bom1`).
- Database: dedicated Supabase project `paylens`, ref `ocpdemjlrlbzytiqerid`, Mumbai. Both Vercel projects connect to `nikhilmyneni/paylens` on GitHub.

Production API settings: sensitive `DATABASE_URL` using the TLS session pooler; `DEMO_MODE=true`; `CORS_ORIGINS=https://paylens-olive.vercel.app`; `EVALUATION_DATA_DIR=evaluation_data`. Frontend setting: `VITE_API_BASE_URL=https://paylens-api.vercel.app`. Rebuild after changing a frontend environment variable.

The dedicated database was migrated and seeded once at full scale: 5,000 employees, 180,000 monthly salary records. Do not rerun generation with `--replace` against this deployment. Bootstrap preserves a populated database.

`backend/evaluation_data` contains only the matching manifest and synthetic labels required for evaluation. Generated source tables and SQL dumps remain excluded. The detector does not read these labels; evaluation verifies source hashes and rejects changed inputs.

After initialization, apply [secure-supabase.sql](../scripts/secure-supabase.sql) as the database owner to enable RLS and revoke direct Data API access. The application accesses PostgreSQL through FastAPI with server-side credentials. The script is for a dedicated Supabase database with `anon` and `authenticated` roles, not vanilla PostgreSQL.

Verify `/ready`, `/api/v1/summary`, `/api/v1/quality`, `/api/v1/evaluation` and the browser review workflow after each release. GitHub CI checks PostgreSQL generation, migration guards, reproducibility and the frontend build. Git-linked Vercel builds are independent of CI; a green deployment does not substitute for a green test run.

This is a synthetic public demo, not production HR authentication. Before using real records, replace demo headers with SSO and server-verified record-level access. Never store credentials in Git or frontend variables. Database owners can bypass RLS and change history triggers; deploy a restricted application database role for real use.
