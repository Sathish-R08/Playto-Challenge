# EXPLAINER — Playto Payout Engine

Short answers the graders asked for, then extra notes (CORS, Celery, tests).

---

## 1) The Ledger

**Paste — balance calculation (database aggregates only)** from [`backend/ledger/balance.py`](backend/ledger/balance.py):

```python
credits = Credit.objects.filter(merchant=merchant).aggregate(
    v=Coalesce(Sum("amount_paise"), 0)
)["v"]

outstanding = (
    Payout.objects.filter(
        merchant=merchant,
        status__in=[
            Payout.Status.PENDING,
            Payout.Status.PROCESSING,
            Payout.Status.COMPLETED,
        ],
    ).aggregate(v=Coalesce(Sum("amount_paise"), 0))["v"]
)

held = (
    Payout.objects.filter(
        merchant=merchant,
        status__in=[Payout.Status.PENDING, Payout.Status.PROCESSING],
    ).aggregate(v=Coalesce(Sum("amount_paise"), 0))["v"]
)

available = credits - outstanding
```

**Why credits + “debits” this way:** Credits are inbound INR (simulated customer payments). There is no separate `Debit` table: **payouts are the debits**. Any payout that is not `failed` represents funds reserved or already sent (`pending` + `processing` + `completed`), so it is summed as **`outstanding`**. **`available_paise = credits − outstanding`** is the invariant the UI shows. **`failed`** payouts are excluded from `outstanding`, so when the worker moves `processing → failed` in one `UPDATE`, the amount immediately stops counting against available — that is how “funds return” without a second money row or Python-side subtraction.

---

## 2) The Lock

**Paste — the serialization point for concurrent POST /payouts** from [`backend/ledger/payout_service.py`](backend/ledger/payout_service.py):

```python
with transaction.atomic():
    m = Merchant.objects.select_for_update().get(pk=merchant.pk)
    # … idempotency replay, then merchant_balance_aggregate(m), then create Payout …
```

Two requests for the **same merchant** cannot both pass the balance check and insert: the second blocks on **`SELECT … FOR UPDATE`** on that merchant row until the first transaction commits. Balance is re-read inside that window via **`merchant_balance_aggregate`** (SQL `SUM`s), not by summing rows in Python.

**Database primitive:** **row-level exclusive lock** on the `Merchant` row (PostgreSQL `FOR UPDATE`; SQLite serializes writers in a single process).

**Worker side:** pending claims use **`select_for_update(skip_locked=True)`** in [`backend/ledger/tasks.py`](backend/ledger/tasks.py) so multiple Celery workers do not double-claim the same payout.

---

## 3) Idempotency

**How we know we’ve seen a key before:** `PayoutIdempotency` has **`UNIQUE (merchant_id, key)`** ([`backend/ledger/models.py`](backend/ledger/models.py)). Under the merchant lock, we **`filter(merchant, key).first()`**; if a row exists and the key is younger than 24h, we return that payout (HTTP 200) without creating another.

**First request in flight, second arrives:** both hit the same merchant lock. The second waits until the first **commits** idempotency + payout rows; then it sees the existing mapping and returns the same payout body. Same key after **24h** → **422** `idempotency_key_expired`, not a duplicate payout.

---

## 4) The State Machine

**Where `failed → completed` is blocked:** [`backend/ledger/state_machine.py`](backend/ledger/state_machine.py) — only these edges are legal; anything else raises **`ValidationError`** before a status `UPDATE`:

```python
def assert_legal_transition(current: str, target: str) -> None:
    allowed = {
        (Payout.Status.PENDING, Payout.Status.PROCESSING),
        (Payout.Status.PROCESSING, Payout.Status.COMPLETED),
        (Payout.Status.PROCESSING, Payout.Status.FAILED),
    }
    if (current, target) not in allowed:
        raise ValidationError(
            f"Illegal payout transition {current!r} -> {target!r}",
            code="illegal_payout_transition",
        )
```

So **`(FAILED, COMPLETED)` is not in `allowed`** — there is no code path that calls `assert_legal_transition(FAILED, COMPLETED)`. The worker only transitions from **`PROCESSING`** using **guarded** `filter(pk=…, status=PROCESSING).update(…)` so a stale read cannot apply a terminal transition twice.

**Funds + failure:** There is no separate balance row. **`failed`** is omitted from the `outstanding` aggregate, so the **same atomic `UPDATE` that sets `status=failed`** is what makes the amount available again.

---

## 5) The AI Audit

**What AI-ish patterns looked tempting (wrong):**

*Wrong — sum balances in Python after `values_list` / list comprehension:*

```python
# BAD: races with concurrent requests; not the same snapshot as the DB sees
credits = sum(Credit.objects.filter(merchant=m).values_list("amount_paise", flat=True))
out = sum(Payout.objects.filter(merchant=m, status__in=held_statuses).values_list(...))
if credits - out < amount:
    return error
```

*Wrong — load model, mutate, `save()` in the worker after two workers might both read `PROCESSING`:*

```python
# BAD: two workers can both "succeed" a transition
p = Payout.objects.get(pk=payout_id)
p.status = Payout.Status.FAILED
p.save()
```

**What was wrong:** (1) Python sums are not locked with the payout insert; another transaction can commit between read and write. (2) `get()` + `save()` is compare-and-set without a database guard — two processes can stomp the same row.

**What we shipped instead:** **`Coalesce(Sum(...))` inside `transaction.atomic()`** after **`select_for_update()`** on the merchant for creates; **`QuerySet.update(...)`** with **`status=PROCESSING`** in the `WHERE` clause for terminal worker transitions; **`SKIP LOCKED`** when claiming pending work.

---

## Additional implementation notes (not graded sections)

### Retry / “stuck in processing”

[`backend/ledger/tasks.py`](backend/ledger/tasks.py): simulated bank outcomes **70% complete / 20% fail / 10% hang**. On **hang**, we bump **`attempt_count`**, set **`processing_started_at`**, and rely on Celery beat re-enqueueing **`simulate_bank_for_payout`**. Before running another simulated call, we enforce **at least 30 seconds** after the last attempt via `BACKOFF_BASE_SECONDS` and `int(30 * (2 ** (attempt_count - 1)))` in `_backoff_seconds` (exponential backoff). After **3** failed “hang” cycles we force **`failed`**.

### CORS

Browsers preflight **`Idempotency-Key`**. [`backend/config/settings.py`](backend/config/settings.py) extends **`CORS_ALLOW_HEADERS`** with **`idempotency-key`**.

### Celery

**Worker + Beat** required; schedule in `CELERY_BEAT_SCHEDULE` (claim pending every 3s, retry processing every 5s).

### Tests

[`backend/pytest.ini`](backend/pytest.ini) uses **`config.settings_test`** (in-memory SQLite by default). **Idempotency** test runs on SQLite; **concurrency** test needs **`USE_POSTGRES_FOR_TESTS=1`** and Postgres (see README).
