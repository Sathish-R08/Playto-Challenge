# Deploy Playto Payout Engine (start → finish)

Your app needs **five runtime pieces**:

| Piece | Role |
|--------|------|
| **Postgres** | Ledger data |
| **Redis** | Celery broker + result backend |
| **Web** | `gunicorn config.wsgi` (Django API) |
| **Worker** | `celery -A config worker` |
| **Beat** | `celery -A config beat` (scheduler) |
| **Static frontend** | `npm run build` → host `frontend/dist` |

**Recommended platform: [Render](https://render.com)** — managed Postgres + Redis + multiple background workers + static sites in one account. Alternatives: **[Railway](https://railway.app)** (similar; good DX), **Fly.io** (more container-oriented).

Free tiers often **sleep** or limit workers; for a demo that must stay up, budget for **Starter** on web + workers or use Railway credits.

---

## A) Render — step by step

### 1. Create Postgres

1. Dashboard → **New +** → **PostgreSQL**.
2. Name it (e.g. `playto-db`), region, plan.
3. After it provisions, copy the **Internal Database URL** (or **External** if Render docs say to use it for your plan). You will set this as `DATABASE_URL` on all Python services.

### 2. Create Redis

1. **New +** → **Redis**.
2. Name it (e.g. `playto-redis`).
3. Copy the **Redis URL** Render shows (often labeled `REDIS_URL` when linked). Use the same value for `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

### 3. Web service (Django API)

1. **New +** → **Web Service** → connect **GitHub** repo `Sathish-R08/Playto-Challenge`.
2. Settings:
   - **Root directory:** `backend`
   - **Runtime:** Python 3
   - **Build command:**  
     `pip install -r requirements.txt && python manage.py collectstatic --noinput --clear`  
     (If collectstatic warns about missing static dirs, you can shorten to `pip install -r requirements.txt` for an API-only deploy.)
   - **Start command:**  
     `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`
3. **Pre-deploy / deploy hook (run migrations):**  
   In Render, add **Pre-Deploy Command** (or run once in **Shell** after first deploy):  
   `python manage.py migrate --noinput`
4. **Environment variables** (Web):

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | Postgres URL from step 1 |
| `CELERY_BROKER_URL` | Redis URL |
| `CELERY_RESULT_BACKEND` | Same as broker |
| `DJANGO_SECRET_KEY` | Long random string (generate new; do not reuse local) |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Your API hostname only, e.g. `playto-api.onrender.com` (no `https://`) |
| `CORS_ALLOW_ALL` | `false` |
| `CORS_ALLOWED_ORIGINS` | Your **frontend** URL(s), comma-separated, e.g. `https://playto-web.onrender.com` |
| `PYTHON_VERSION` | e.g. `3.12.3` (match what you use locally) |

5. Deploy. Open `https://<your-service>.onrender.com/api/v1/balance/` — expect **401** without `Authorization` (proves the app is up).

### 4. Background Worker (Celery worker)

1. **New +** → **Background Worker** → same repo.
2. **Root directory:** `backend`
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `celery -A config worker -l info`
5. **Environment:** copy the **same** variables as the Web service (`DATABASE_URL`, Redis URLs, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, etc.). Workers import Django settings and need DB + secret.

### 5. Second Background Worker (Celery beat)

1. **New +** → **Background Worker** → same repo.
2. **Root directory:** `backend`
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `celery -A config beat -l info`
5. **Environment:** same as Web again.

### 6. Static site (React)

Do this **after** the API has a public URL.

1. **New +** → **Static Site** → same repo.
2. **Root directory:** `frontend`
3. **Build command:** `npm install && npm run build`
4. **Publish directory:** `dist`
5. **Environment variables** (build-time — Vite bakes these in):

| Variable | Example |
|----------|---------|
| `VITE_API_BASE_URL` | `https://playto-api.onrender.com` — **no trailing slash** |
| `VITE_MERCHANT_API_KEY` | `demo-token-alpha` (or leave default until after seed) |

6. Redeploy static site whenever you change API URL or merchant token.

### 7. Seed data (one time)

Render **Web** → **Shell** (or local with production `DATABASE_URL`):

```bash
cd backend
python manage.py seed_playto
```

Copy the printed Bearer tokens; update `VITE_MERCHANT_API_KEY` + rebuild static site if you change tokens.

### 8. Checklist (avoid common mistakes)

- [ ] `DJANGO_ALLOWED_HOSTS` matches the **host** part of your API URL only.
- [ ] `CORS_ALLOWED_ORIGINS` includes your **exact** frontend origin (`https://...`).
- [ ] `CORS_ALLOW_ALL` is **false** in production.
- [ ] Worker and Beat both deployed and **not** crashing (check logs).
- [ ] Redis URL uses the format Celery expects (`rediss://` if TLS — use the string Render gives you).
- [ ] Frontend built with `VITE_API_BASE_URL` pointing at **HTTPS API**, not `localhost`.

---

## B) Railway (summary)

1. New project → **Deploy from GitHub** → this repo.
2. Add **PostgreSQL** and **Redis** plugins.
3. Create **three services** from the same repo, root `backend`:
   - Service A start: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` (Railway sets `PORT`).
   - Service B start: `celery -A config worker -l info`
   - Service C start: `celery -A config beat -l info`
4. Set the same Django/Redis/Postgres env vars on all three (Railway often injects `DATABASE_URL` / `REDIS_URL` — map them to `CELERY_BROKER_URL` if needed).
5. Frontend: add a **static** or **second deploy** from `frontend` with `npm run build`, serve `dist`, with build args for `VITE_*`.

---

## C) After deploy

- Submit the **frontend URL** and **API base URL** in the challenge form.
- Run a quick test: dashboard loads, balance JSON works with Bearer token, submit payout returns 201/200.

---

## Optional: Blueprint

See [`render.yaml`](render.yaml) in this repo ([Render Blueprint spec](https://render.com/docs/blueprint-spec)). It uses an **environment group** so **web, worker, and beat share the same `DJANGO_SECRET_KEY`**, `DJANGO_ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS`. You still run `seed_playto` once in a shell after the first deploy.

If the Blueprint apply flow asks for values: **`DJANGO_ALLOWED_HOSTS`** = API hostname only (e.g. `playto-api.onrender.com`); **`CORS_ALLOWED_ORIGINS`** = your static site origin (e.g. `https://playto-frontend.onrender.com`); **`VITE_API_BASE_URL`** = public API base URL (e.g. `https://playto-api.onrender.com`, no trailing slash). Redeploy the static site after the API URL is final.
