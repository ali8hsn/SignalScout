# Deploying Signal Scout to Railway

Railway is like Vercel but for long-running servers: instead of serverless functions it runs
your Dockerfile as an always-on process, and Postgres + cron live in the same project.
One service serves both the API and the built frontend, so there is one public URL and no CORS.

## 0. Prerequisites

- The repo pushed to GitHub (`ali8hsn/signalScout`).
- A [railway.com](https://railway.com) account (sign in with GitHub — free trial is enough to start).
- The Railway CLI for the one-off migration step: `npm i -g @railway/cli` (or `brew install railway`).

## 1. Test the container locally (optional but recommended)

```bash
docker build -t signal-scout .
docker run --rm -p 8000:8000 -v "$PWD/signal_scout.db:/app/signal_scout.db" signal-scout
# In another terminal:
curl http://localhost:8000/api/health     # → {"status":"ok","db":"sqlite"}
open http://localhost:8000                # the built frontend
```

(The `-v` mount gives the container your local SQLite DB; in production Postgres is used instead.)

## 2. Create the project from the GitHub repo

1. Go to [railway.com/new](https://railway.com/new) → click **Deploy from GitHub repo**.
2. Authorize Railway's GitHub app if prompted, then pick **ali8hsn/signalScout**.
3. Click **Deploy now**. Railway detects the `Dockerfile` automatically and builds it
   (like Vercel's build step; watch progress under the service's **Deployments** tab).
4. The first deploy can build before Postgres exists. The frontend and SQLite health check can
   load, but data endpoints are not ready until the Postgres variable and migration below finish.

## 3. Add the Postgres plugin

1. Return to the project canvas and click **+ Create** → **Database** → **Add PostgreSQL**.
2. A `Postgres` service appears next to your app service. Nothing else to configure.

## 4. Set environment variables

1. Click your **app service** (not Postgres) → **Variables** tab → **+ New Variable**.
2. Click **Add Reference**, choose the **Postgres** service, and select `DATABASE_URL`. Confirm the
   app variable is named `DATABASE_URL` and displays `${{Postgres.DATABASE_URL}}`.
3. Add the rest from `.env.example` as needed:
   - `GITHUB_TOKEN` — enables the live "Run Discovery" pipeline.
   - `ENRICHMENT_PROVIDER`, `PDL_API_KEY` / `CORESIGNAL_API_KEY`, `DAILY_ENRICHMENT_BUDGET` — LinkedIn enrichment.
   - `RESEND_API_KEY`, `DIGEST_FROM_EMAIL`, `PUBLIC_BASE_URL`, `CRON_SECRET` — email digest.
     Set `PUBLIC_BASE_URL` to the generated Railway origin, for example
     `https://signalscout-production.up.railway.app` (no trailing slash).
   - `SIGNAL_SCOUT_DB` is **not** needed on Railway (Postgres is used when `DATABASE_URL` is set).
4. Click **Deploy** on the banner that appears — variable changes trigger a redeploy.

## 5. Run the data migration

This copies every table (founders, discoveries, signals, edges, digests) from your local
`signal_scout.db` into Railway's Postgres. Run it from the repo root on your machine:

```bash
railway login
railway link          # choose the Signal Scout project, production environment, and app service
railway run --service <app-service-name> python scripts/migrate_sqlite_to_postgres.py
```

`railway run` executes the command locally with the service's environment variables injected,
so it reads your local SQLite file and writes to the hosted Postgres.

Preview what would be copied without touching Postgres:

```bash
python scripts/migrate_sqlite_to_postgres.py --dry-run
```

The migration is idempotent and transactional: it truncates the destination set, copies every
discovered SQLite table, verifies each row count, and rolls back if any table fails.

> If `DATABASE_URL` in the service references the plugin's *private* network URL and the
> migration can't connect from your laptop, copy the **public** connection string instead:
> Postgres service → **Connect** tab → *Public network* → run
> `DATABASE_URL='<that url>' python scripts/migrate_sqlite_to_postgres.py`.

## 6. Generate a public domain

1. App service → **Settings** tab → **Networking** section → **Generate Domain**.
2. When asked for the port, enter **8000** (the Dockerfile default; Railway also injects `$PORT`).
3. Click **Generate Domain**. Copy the URL, such as
   `https://signalscout-production.up.railway.app`.

## 7. Verify

```bash
curl https://<your-domain>/api/health     # → {"status":"ok","db":"postgres"}
curl https://<your-domain>/api/overview   # → backtest stats + discovery counts
```

Open the root URL in a browser — the full frontend (Discover / Backtest / Digest) should load
with all migrated data, no login.

## 8. Configure Resend and the daily digest cron

1. In Resend, verify the domain used by `DIGEST_FROM_EMAIL`, create an API key, and add both
   values to the app service. Resend controls open tracking at the domain level rather than in
   the send-email API payload: open the domain's settings and leave **Open tracking** enabled.
   With either value missing, Signal Scout safely renders previews and records no sends.
2. Railway cron jobs execute commands. Project canvas → **+ Create** → **Empty Service**, name it
   `digest-cron`, connect it to the same GitHub repo, and copy the app service variables
   (`DATABASE_URL`, `RESEND_API_KEY`, `DIGEST_FROM_EMAIL`, and `PUBLIC_BASE_URL`).
3. Service **Settings** → set its start command to `python scripts/send_digests.py`.
4. Set **Cron Schedule** to `0 15 * * *` (15:00 UTC = 8:00 AM PDT). Railway schedules in UTC
   and does not follow DST, so this runs at 7:00 AM PST in winter; use `0 16 * * *` then if
   8 AM local delivery matters. The command sends daily subscriptions every run and weekly
   subscriptions only on Monday.

The always-on app also exposes an equivalent endpoint protected by the exact header
`Authorization: Bearer $CRON_SECRET`. Use dry-run first; it renders the selected subscriber's
HTML/plain-text preview but does not call Resend or consume candidates:

```bash
curl -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "https://<your-domain>/api/digest/cron?dry_run=true&recipient=you@example.com"

# Real manual run for one active subscriber:
curl -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "https://<your-domain>/api/digest/cron?recipient=you@example.com"
```

For a local command-path preview, run
`python scripts/send_digests.py --dry-run --recipient you@example.com`.

## Troubleshooting

- **Build fails on `npm ci`** — make sure `frontend/package-lock.json` is committed.
- **`/api/health` returns 500** — check `DATABASE_URL` is a valid reference (Variables tab shows
  the resolved value); the app falls back to SQLite (empty in the container) only when it's unset.
- **Frontend 404s** — the container serves `frontend/dist` built during the Docker build; check the
  build logs' frontend stage. API routes always win because they're mounted before the static files.
- **Logs** — service → **Deployments** → click the active deployment → **View Logs**
  (equivalent of `vercel logs`).
