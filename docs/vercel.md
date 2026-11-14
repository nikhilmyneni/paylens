# Vercel deployment plan

Use two Vercel projects from this repository and a separate managed PostgreSQL database. Vercel's [monorepo guide](https://vercel.com/docs/monorepos) describes assigning a different root directory to each project; its [FastAPI guide](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel) recognizes `backend/main.py` as an API entry point.

1. Connect the intended Vercel account and import the repository twice. Set the API project's root directory to `backend/` and the UI project's root directory to `frontend/`.
2. Provision PostgreSQL through a [Vercel Marketplace storage integration](https://vercel.com/docs/marketplace-storage) or an equivalent managed provider. Set the API project's `DATABASE_URL` to the provider's connection string. The backend normalizes `postgresql://` to the installed psycopg 3 driver.
3. From a trusted local machine, run `python backend/generate.py --scale starter --database-url <DATABASE_URL> --output data/generated/starter` once against the new, empty database. Do not run a data generator during a serverless request.
4. Set API `CORS_ORIGINS` to the final UI HTTPS origin and `DEMO_MODE=true` for the synthetic demonstration. Set UI build variable `VITE_API_BASE_URL` to the final API HTTPS origin, then rebuild the UI. The browser needs the public API URL at build time.
5. Check API `/ready`, `/api/v1/summary` and `/docs`; then verify the UI review queue, evidence drawer and proposal transitions from the deployed UI domain.

`DEMO_MODE=true` accepts demo role headers and must only expose synthetic records. For real compensation records, replace demo access with organization SSO and server-verified roles. The generator refuses to overwrite a populated database unless explicitly called with `--replace` in demo mode. Keep database credentials in Vercel environment settings; never commit them.

Deployment uses the nikhilmyneni CLI accounts and a dedicated PayLens database. Configure credentials locally or in provider environment settings, never in Git.
