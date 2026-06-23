# Deploy to Render (native Python, no Docker)

One **Render Web Service** runs the FastAPI backend **and** serves the built React
SPA from the same URL — `/v1/*` is the API, everything else is the app. No
Dockerfile (Render builds the Python env + runs the SPA build for you).

Blueprint: [`render.yaml`](../render.yaml).

## What it does
- **Build:** `pip install -r requirements.txt && npm ci && npm run build` (the SPA
  builds to `<repo>/dist`; Render's build image includes Node).
- **Run:** `python -m uvicorn src.api:app --host 0.0.0.0 --port $PORT`.
- **`SERVE_SPA=1`** → FastAPI serves `dist/` at root and mounts the API at `/v1`
  only (so the SPA owns the page routes). The app's `API_BASE` is already `/v1`,
  so it's same-origin — no CORS needed.
- **Persistent disk** at `/var/data` (`STORAGE_DIR`) keeps saved connections /
  schemas / reports across deploys. *(Requires a paid plan; on `free` the disk is
  unavailable and that data resets on every redeploy — you'd just re-add the
  connection each time.)*

## Steps
1. **Get the code on a Git remote Render can read** (GitHub/GitLab).
   ⚠️ **Push freeze:** pushing branch `v2` to the existing `origin`
   (`ratishkp83/ask-oracle2`) triggers its GitHub Actions and is on hold until the
   July reset. Until then, deploy from a **separate repo without the
   `.github/workflows/` directory** (so no Actions run) — e.g. push `v2` to a new
   private repo and connect Render to that. (Or wait for July.)
2. Render Dashboard → **New → Blueprint** → pick the repo/branch → it reads
   `render.yaml`.
3. Set the **secret** env vars (everything marked `sync: false`):
   - `APP_SECRET_KEY` — generate once:
     `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
     (keep it; changing it invalidates all saved connections).
   - `GROQ_API_KEY` — your Groq key.
   - *(optional)* `APP_API_KEY`, `SMTP_*` for email.
4. **Apply** → first build + deploy. Health check is `/v1/health`.
5. Open the service URL → add your **Supabase** connection in **Connections**
   (engine *PostgreSQL/Supabase*; use the **direct** host `db.<ref>.supabase.co`
   :5432, user `postgres`, or the **session pooler** `aws-0-<region>.pooler.
   supabase.com:5432`, user `postgres.<ref>` if your network is IPv4-only).

## Keep the connection across restarts on the free tier (env-seed)
The free plan has **no persistent disk**, so a saved connection is lost whenever the
instance **sleeps (~15m idle) or redeploys**. Instead of re-adding it by hand each
time, set the `SEED_*` env vars and the app **recreates the connection on every boot**:

| Var | Value (Supabase) |
|---|---|
| `SEED_HOST` | Session pooler host, e.g. `aws-1-<region>.pooler.supabase.com` |
| `SEED_USERNAME` | `postgres.<project-ref>` |
| `SEED_PASSWORD` | your Supabase DB password |
| `SEED_DATABASE` | `postgres` · `SEED_PORT` `5432` · `SEED_SSLMODE` `require` · `SEED_SCHEMA` `public` · `SEED_ENGINE` `postgres` · `SEED_PROFILE_NAME` `Supabase` |

The non-secret defaults are pre-declared in `render.yaml`; set the three secrets
(`SEED_HOST`/`SEED_USERNAME`/`SEED_PASSWORD`) in the dashboard. The password lives
only in the platform's env (never the repo) and is encrypted at rest exactly like a
UI-added profile (invariant 4). Seeding is **idempotent** — a no-op when a profile of
that name already exists, so it's safe on a paid disk too. After seeding, you still
**"Read from database"** once to register the schema (the schema store is also
ephemeral on free; the connection is what env-seed restores). Leave the `SEED_*` vars
unset to disable.

## Security (important for a public URL)
The app has no login yet (RISK-07). Options:
- **Personal/demo:** leave `APP_API_KEY` unset and keep the URL private. Anyone with
  the URL can use it (and reach any saved connection), so don't share it widely.
- **Lock it down without building auth:** put the service behind **Cloudflare
  Access** (or a Render IP allow-list / a VPN). This is the recommended way to make
  it private.
- **`APP_API_KEY`** gates the `/v1` API, but the SPA must ship `VITE_AOR_API_KEY`
  (build arg) to call it — and that key is then visible in the public bundle, so it
  only deters casual scanners, not a determined user. Use platform-level access
  control for real privacy.

## Notes
- **Region:** set `region:` (and your Supabase region) close together to cut
  latency. Default in the blueprint is `singapore` (matches an `ap-southeast-1`
  Supabase).
- **If the build can't find `npm`:** Render's native build image normally includes
  Node, but if not, either (a) build the SPA locally (`npm run build`) and commit
  `dist/` for the deploy branch, or (b) split into a Render **Static Site** for the
  SPA + this service for the API (set the static site's `VITE_AOR_API_BASE` to the
  API URL + `/v1` and the API's `ALLOWED_ORIGINS` to the static-site URL).
- **Streamlit admin (optional):** the legacy Streamlit UI can be added as a second
  `type: web` service (`startCommand: streamlit run src/app.py --server.port=$PORT
  --server.address=0.0.0.0 --server.headless=true`) sharing the same env — but the
  React surface already covers connections/dictionary/reports/ask/settings.
- **Cost:** `starter` web service + 1 GB disk ≈ a few USD/month. The `free` plan
  works for a quick look but loses saved data on redeploy.
