# Playto Payout Engine (challenge submission)

Minimal merchant ledger + payout request API + Celery processor + React dashboard, aligned with the **Playto Founding Engineer Challenge** brief.

## Stack

- Backend: **Django** (5.x or 6.x, see `requirements.txt`), **DRF**, **PostgreSQL** (recommended for production and the concurrency test), **Celery + Redis**
- Frontend: **Vite + React + Tailwind**
- Money: **integer paise** only (`BigIntegerField`)

## Rubric alignment (Playto brief)

| Requirement | Where it lives |
|-------------|----------------|
| Ledger in paise, balance from **DB `Sum`s** | [`backend/ledger/balance.py`](backend/ledger/balance.py) |
| POST `/api/v1/payouts/` + **`Idempotency-Key`**, 24h scope per merchant | [`backend/ledger/payout_service.py`](backend/ledger/payout_service.py), [`backend/ledger/views.py`](backend/ledger/views.py) |
| Concurrency: two oversized payouts → one success | Postgres + [`ledger/tests/test_payout_api.py`](backend/ledger/tests/test_payout_api.py) (`USE_POSTGRES_FOR_TESTS=1`) |
| Celery processor, 70/20/10, not sync-only | [`backend/ledger/tasks.py`](backend/ledger/tasks.py) + Beat schedule in [`backend/config/settings.py`](backend/config/settings.py) |
| Retry: ≥30s before retry, backoff, max 3 hangs → failed | [`backend/ledger/tasks.py`](backend/ledger/tasks.py) (`BACKOFF_BASE_SECONDS`, `MAX_BANK_ATTEMPTS`) |
| State machine + guarded `UPDATE`s | [`backend/ledger/state_machine.py`](backend/ledger/state_machine.py), tasks |
| React dashboard: balance, held, credits, debits (payouts), live refresh | [`frontend/src/App.jsx`](frontend/src/App.jsx) (poll ~3s) |
| Seed 2–3 merchants | `python manage.py seed_playto` |
| **EXPLAINER** answers (ledger, lock, idempotency, state machine, AI audit) | [`EXPLAINER.md`](EXPLAINER.md) |

## Quick start (local)

### 1) Postgres + Redis

Use the included [`docker-compose.yml`](docker-compose.yml) **or** any managed Postgres/Redis.

```bash
docker compose up -d
```

Default compose credentials: user **`playto`**, password **`playto`**, database **`playto`**. Copy [`.env.example`](.env.example) to `backend/.env` and adjust if needed.

### 2) Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy ..\.env.example .env
# Edit backend/.env — at minimum DATABASE_URL and Redis URLs

python manage.py migrate
python manage.py seed_playto

python manage.py runserver 0.0.0.0:8000
```

In **two more terminals** (same `backend` venv and env vars):

```bash
celery -A config worker -l info
```

```bash
celery -A config beat -l info
```

**Windows:** The default **prefork** Celery pool often crashes with `PermissionError: [WinError 5] Access is denied` (billiard semaphores). This repo defaults to **`CELERY_WORKER_POOL=solo`** on Windows in [`backend/config/settings.py`](backend/config/settings.py) so the worker still uses Redis but runs tasks in one process. On Linux/production you can set `CELERY_WORKER_POOL=prefork`.

**Celery Beat** writes `celerybeat-schedule*` SQLite files under `backend/`. Those files are **gitignored**; stop `beat` if you need to delete them and the OS reports “file in use”.

### 3) Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
# Set VITE_API_BASE_URL and VITE_MERCHANT_API_KEY (see seed_playto output)
npm run dev
```

Open the Vite URL (usually `http://localhost:5173` or `http://127.0.0.1:5173`).

**CORS:** The API allows the browser `Authorization` and **`Idempotency-Key`** headers via `CORS_ALLOW_HEADERS` in settings. For production, set `CORS_ALLOW_ALL=false` and list origins in `CORS_ALLOWED_ORIGINS` (comma-separated in `backend/.env`).

## Tests

```bash
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

By default, pytest uses [`backend/config/settings_test.py`](backend/config/settings_test.py) (**in-memory SQLite**) via [`backend/pytest.ini`](backend/pytest.ini), so you do not need Postgres or `CREATEDB` privileges to run the suite locally or in CI. [`backend/conftest.py`](backend/conftest.py) sets `CELERY_TASK_ALWAYS_EAGER` so tasks run inline in tests.

- **Idempotency** test runs on SQLite.
- **Concurrency** test is **skipped on SQLite** (threaded row locks differ). To run it against Postgres:

```bash
set USE_POSTGRES_FOR_TESTS=1
set DATABASE_URL=postgresql://playto:playto@127.0.0.1:5432/playto
pytest -q
```

The Postgres role must be allowed to **create** the test database (e.g. `ALTER ROLE playto CREATEDB;` for local dev), or use a superuser URL for tests only.

## API

All endpoints require:

`Authorization: Bearer <merchant api_token>`

`seed_playto` prints three demo tokens (`demo-token-alpha`, …).

- `GET /api/v1/balance/`
- `GET /api/v1/credits/`
- `GET /api/v1/payouts/`
- `POST /api/v1/payouts/` with header `Idempotency-Key: <uuid>` and JSON body:

```json
{ "amount_paise": 10000, "bank_account_id": "your-bank-ref" }
```

## Security & GitHub

- **`backend/.env`**, **`frontend/.env.local`**, and local DB/beat files are **gitignored**. Use **`.env.example`** / **`frontend/.env.example`** only for non-secret templates.
- For a public repo: rotate any keys that ever appeared in committed files; never commit real `DJANGO_SECRET_KEY` or database passwords.

## Deploy (Render / Railway / Fly)

Provision **web** (Gunicorn `config.wsgi`), **worker** (`celery -A config worker`), **beat** (`celery -A config beat`), **Postgres**, **Redis**.

Set at least: `DATABASE_URL`, `CELERY_BROKER_URL`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS` (your API hostnames), `CORS_ALLOW_ALL=false`, `CORS_ALLOWED_ORIGINS` (your frontend origins, comma-separated).

Build the frontend with `npm run build` and host `frontend/dist/` as a static site; rebuild with `VITE_API_BASE_URL` pointing at your public API origin (or configure your CDN/reverse proxy).

## EXPLAINER

See [`EXPLAINER.md`](EXPLAINER.md) for the design write-up (ledger, locking, idempotency, state machine, CORS, Celery schedule, testing defaults).
