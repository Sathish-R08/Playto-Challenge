# Playto Payout Engine (challenge submission)

Minimal merchant ledger + payout request API + Celery processor + React dashboard, aligned with the **Playto Founding Engineer Challenge** brief.

**This repo is meant to run fully on your machine** (Docker + Python + Node). You do **not** need a paid cloud account to review or demo the code—clone, follow **Run everything locally** below, and open the dashboard in a browser.

## Stack

- Backend: **Django** (5.x or 6.x, see `requirements.txt`), **DRF**, **PostgreSQL**, **Celery + Redis**
- Frontend: **Vite + React + Tailwind**
- Money: **integer paise** only (`BigIntegerField`)

## Prerequisites

- **Docker Desktop** (or Docker Engine + Compose) for Postgres + Redis  
- **Python 3.12+** (3.11+ usually works)  
- **Node.js 18+** and npm  

---

## Run everything locally (step by step)

You will end up with **four** long-running processes: **Postgres + Redis** (Docker), **Django**, **Celery worker**, **Celery beat**, plus **Vite** for the UI.

### Step 0 — Clone and open the repo

```bash
git clone <your-repo-url>
cd Playto-Challenge   # or whatever you named the folder
```

### Step 1 — Start Postgres and Redis (Docker)

From the **repository root** (where `docker-compose.yml` lives):

```bash
docker compose up -d
```

Wait until both containers are healthy. Default DB (see `docker-compose.yml`):

- User: `playto`  
- Password: `playto`  
- Database: `playto`  
- Port: `5432`  

Redis: `127.0.0.1:6379`

**Stop later:** `docker compose down` (add `-v` only if you want to wipe DB data).

### Step 2 — Backend environment file

Copy the template into `backend/.env`:

**Windows (PowerShell), from repo root:**

```powershell
Copy-Item ..\.env.example .env
```

Run that **after** `cd backend`, or copy from root:

```powershell
Copy-Item .env.example backend\.env
```

**macOS / Linux:**

```bash
cp .env.example backend/.env
```

The values in [`.env.example`](.env.example) already match `docker-compose.yml`. Edit `backend/.env` only if you changed Docker credentials or ports.

### Step 3 — Python venv, migrate, seed

```bash
cd backend
python -m venv .venv
```

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_playto
```

**macOS / Linux:**

```bash
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_playto
```

`seed_playto` prints **Bearer tokens** (e.g. `demo-token-alpha`). Keep one for the frontend.

### Step 4 — Django API (terminal 1)

Still in `backend` with venv **activated**:

```bash
python manage.py runserver 0.0.0.0:8000
```

Check: open [http://127.0.0.1:8000/api/v1/balance/](http://127.0.0.1:8000/api/v1/balance/) — you should see **401 Unauthorized** (proves the app is up; API requires Bearer token).

### Step 5 — Celery worker (terminal 2)

New terminal, **same** `backend` folder, **same** venv activate, **same** `backend/.env` (Django reads it automatically):

```bash
cd backend
# activate venv again
celery -A config worker -l info
```

**Windows:** This repo defaults to the **`solo`** pool on Windows to avoid Celery/billiard `WinError 5`. Linux/macOS can use `prefork` via `CELERY_WORKER_POOL=prefork` in `.env` if you want.

### Step 6 — Celery beat (terminal 3)

Another terminal, same pattern:

```bash
cd backend
# activate venv
celery -A config beat -l info
```

Beat may create `celerybeat-schedule*` files under `backend/` (gitignored). Stop beat before deleting them if Windows says “file in use”.

### Step 7 — Frontend (terminal 4)

```bash
cd frontend
npm install
```

Copy env template to `.env.local`:

**Windows:** `Copy-Item .env.example .env.local`  
**macOS / Linux:** `cp .env.example .env.local`

Set at least:

- `VITE_API_BASE_URL=http://127.0.0.1:8000` (must match where `runserver` listens)  
- `VITE_MERCHANT_API_KEY=demo-token-alpha` (or another token from `seed_playto`)

Start Vite:

```bash
npm run dev
```

Open the URL Vite prints (usually [http://localhost:5173](http://localhost:5173)). You should see balances, credits, payout form, and history updating every few seconds. Submit a small payout and watch status move **pending → processing → completed/failed** (worker + beat must be running).

---

## Quick verification checklist

| Check | Expected |
|--------|----------|
| Docker | `docker compose ps` shows `db` and `redis` up |
| API | `/api/v1/balance/` returns 401 without `Authorization` |
| Dashboard | Loads with Bearer token from `.env.local` |
| Payouts | With worker + beat running, new payouts eventually leave `pending` |

---

## Tests

```bash
cd backend
# activate venv
pytest -q
```

By default this uses **in-memory SQLite** ([`backend/config/settings_test.py`](backend/config/settings_test.py), [`backend/pytest.ini`](backend/pytest.ini))—no extra DB setup. **Idempotency** runs; **concurrency** is **skipped** on SQLite.

**Concurrency test on Postgres** (Docker DB must be up; role needs permission to create test DB, or use a superuser test URL):

**Windows:**

```powershell
$env:USE_POSTGRES_FOR_TESTS="1"
$env:DATABASE_URL="postgresql://playto:playto@127.0.0.1:5432/playto"
pytest -q
```

**macOS / Linux:**

```bash
USE_POSTGRES_FOR_TESTS=1 DATABASE_URL=postgresql://playto:playto@127.0.0.1:5432/playto pytest -q
```

---

## Rubric alignment (Playto brief)

| Requirement | Where it lives |
|-------------|----------------|
| Ledger in paise, balance from **DB `Sum`s** | [`backend/ledger/balance.py`](backend/ledger/balance.py) |
| POST `/api/v1/payouts/` + **`Idempotency-Key`**, 24h per merchant | [`backend/ledger/payout_service.py`](backend/ledger/payout_service.py), [`backend/ledger/views.py`](backend/ledger/views.py) |
| Concurrency: two oversized payouts → one success | Postgres + [`backend/ledger/tests/test_payout_api.py`](backend/ledger/tests/test_payout_api.py) |
| Celery processor, 70/20/10 | [`backend/ledger/tasks.py`](backend/ledger/tasks.py) + [`backend/config/settings.py`](backend/config/settings.py) (`CELERY_BEAT_SCHEDULE`) |
| Retry / backoff / max attempts | [`backend/ledger/tasks.py`](backend/ledger/tasks.py) |
| State machine + guarded `UPDATE`s | [`backend/ledger/state_machine.py`](backend/ledger/state_machine.py) |
| React dashboard | [`frontend/src/App.jsx`](frontend/src/App.jsx) |
| Seed 2–3 merchants | `python manage.py seed_playto` |
| **EXPLAINER** | [`EXPLAINER.md`](EXPLAINER.md) |

---

## API (short)

All endpoints require: `Authorization: Bearer <merchant api_token>`

- `GET /api/v1/balance/`
- `GET /api/v1/credits/`
- `GET /api/v1/payouts/`
- `POST /api/v1/payouts/` with header `Idempotency-Key: <uuid>` and JSON `{ "amount_paise": 10000, "bank_account_id": "..." }`

**CORS:** Local dev uses `CORS_ALLOW_ALL=true` in `.env.example`. The API allows the **`idempotency-key`** header (see [`backend/config/settings.py`](backend/config/settings.py)).

---

## Submitting without paid cloud hosting

The challenge may ask for a **public URL**. If you do **not** deploy:

- This README is enough for reviewers to **clone and run the full stack locally** (or on their own infra).  
- In your submission, you can say you’re providing a **reproducible local setup** and offer a **short screen-share demo** if they want to see it live.

Optional later: deploy API + worker + beat + Redis + Postgres + static frontend on Render/Railway/Fly (all typically need **multiple** billable or credit-backed services for 24/7).

---

## Security & GitHub

- **`backend/.env`**, **`frontend/.env.local`**, and local DB/beat artifacts are **gitignored**.  
- Never commit real secrets; use [`.env.example`](.env.example) and [`frontend/.env.example`](frontend/.env.example) as templates only.

---

## EXPLAINER

See [`EXPLAINER.md`](EXPLAINER.md) for the design write-up (ledger, locking, idempotency, state machine, AI audit).
