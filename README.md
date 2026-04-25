# Playto Payout Engine (challenge submission)

Minimal merchant ledger + payout request API + Celery processor + React dashboard, aligned with the **Playto Founding Engineer Challenge 2026** brief.

## Stack

- Backend: **Django 6**, **DRF**, **PostgreSQL** (production / graded tests), **Celery + Redis**
- Frontend: **Vite + React + Tailwind**
- Money: **integer paise** only (`BigIntegerField`)

## Quick start (local)

### 1) Postgres + Redis

Use the included [`docker-compose.yml`](docker-compose.yml) **or** any managed Postgres/Redis.

```bash
docker compose up -d
```

Default compose credentials match [`.env.example`](.env.example).

### 2) Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

set DATABASE_URL=postgresql://playto:playto@127.0.0.1:5432/playto
set CELERY_BROKER_URL=redis://127.0.0.1:6379/0
set CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

python manage.py migrate
python manage.py seed_playto

python manage.py runserver 0.0.0.0:8000
```

In **two more terminals** (same env vars):

```bash
celery -A config worker -l info
```

```bash
celery -A config beat -l info
```

### 3) Frontend

```bash
cd frontend
npm install
copy ..\\.env.example .env.local
# edit .env.local: VITE_API_BASE_URL and VITE_MERCHANT_API_KEY (see seed output)
npm run dev
```

Open the Vite URL (usually `http://127.0.0.1:5173`).

## Tests

```bash
cd backend
.\.venv\Scripts\Activate.ps1
pytest -q
```

- **Idempotency** test runs on SQLite or Postgres.
- **Concurrency** test is **skipped on SQLite** (file locking / semantics differ). Run it against Postgres:

```bash
set DATABASE_URL=postgresql://playto:playto@127.0.0.1:5432/playto
pytest -q
```

## API

All endpoints require:

`Authorization: Bearer <merchant api_token>`

Seed prints three demo tokens (`demo-token-alpha`, …).

- `GET /api/v1/balance/`
- `GET /api/v1/credits/`
- `GET /api/v1/payouts/`
- `POST /api/v1/payouts/` with headers `Idempotency-Key: <uuid>` and JSON body:

```json
{ "amount_paise": 10000, "bank_account_id": "your-bank-ref" }
```

## Deploy (Render / Railway / Fly)

Provision **web** (Gunicorn `config.wsgi`), **worker** (`celery -A config worker`), **beat** (`celery -A config beat`), **Postgres**, **Redis**. Set the same env vars as local (`DATABASE_URL`, `CELERY_BROKER_URL`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, …). Build the frontend with `npm run build` and host `frontend/dist/` as a static site; point `VITE_API_BASE_URL` at your public API origin.

## EXPLAINER

See [`EXPLAINER.md`](EXPLAINER.md) for the graded write-up (ledger query, locking, idempotency, state machine, AI audit).
