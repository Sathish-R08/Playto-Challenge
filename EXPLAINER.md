# EXPLAINER — Playto Payout Engine

## 1) The Ledger

**Balance calculation (DB aggregates only)** lives in [`backend/ledger/balance.py`](backend/ledger/balance.py):

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

**Why this shape:** `Credit` rows are inbound customer payments (simulated). Any payout that is **pending**, **processing**, or **completed** is money reserved or already paid out, so it belongs in one **outstanding** sum. **`available`** is therefore a single auditable expression: **credits minus all non-failed payouts**. **`held`** is only a UI slice of outstanding (pending + processing).

---

## 2) The Lock

**API concurrency (two simultaneous payout requests):** [`backend/ledger/payout_service.py`](backend/ledger/payout_service.py) opens `transaction.atomic()`, then:

```python
m = Merchant.objects.select_for_update().get(pk=merchant.pk)
```

All balance checks and inserts for that merchant’s payout happen while this row is locked, so another request for the **same merchant** blocks on **`SELECT … FOR UPDATE`** until the first transaction commits. The primitive is **Postgres row-level locking** via Django’s `select_for_update()`.

**Worker concurrency (two Celery workers):** [`backend/ledger/tasks.py`](backend/ledger/tasks.py) claims work with:

```python
Payout.objects.filter(status=Payout.Status.PENDING)
    .select_for_update(skip_locked=True)
```

**Why `SKIP LOCKED` matters:** without it, two workers can end up contending on the same `pending` row in ways that are easy to get wrong (duplicate processing, double side effects). `SKIP LOCKED` makes workers **skip rows already locked** and grab the next pending payout instead.

---

## 3) Idempotency

**How we know we’ve seen a key before:** `UNIQUE(merchant_id, key)` on `PayoutIdempotency`, plus a normal lookup under the merchant lock for replays.

**Same key within 24 hours:** return the same serialized `Payout` (`200`) — no second payout.

**Expired key (>24 hours):** `422` with `{"code":"idempotency_key_expired",...}` — **not** the original success body.

**First request in-flight + second arrives:** both requests serialize on the **merchant `select_for_update()`** for that merchant. The second observes the committed idempotency + payout row and returns the same payout payload.

**Poisoned keys:** the idempotency row + payout row are created in the **same** `transaction.atomic()` block as the balance check. If anything fails, **everything rolls back** — we never commit an idempotency row without its payout.

---

## 4) The State Machine

Illegal transitions are rejected centrally in [`backend/ledger/state_machine.py`](backend/ledger/state_machine.py):

```python
allowed = {
    (Payout.Status.PENDING, Payout.Status.PROCESSING),
    (Payout.Status.PROCESSING, Payout.Status.COMPLETED),
    (Payout.Status.PROCESSING, Payout.Status.FAILED),
}
```

So **`failed -> completed` is impossible** (not in `allowed`). The worker calls `assert_legal_transition(...)` before guarded status updates.

**Atomic failure / completion (no double-free):** worker transitions use guarded updates, e.g.:

```python
updated = Payout.objects.filter(pk=p.pk, status=Payout.Status.PROCESSING).update(
    status=Payout.Status.FAILED,
    attempt_count=next_attempt,
    last_error="simulated_bank_failure",
)
if updated == 0:
    logger.info("payout %s failed transition skipped (race)", payout_id)
```

This relies on the DB to apply **0 or 1** row updates for the terminal transition, instead of `obj.save()` after a stale read.

---

## 5) AI Audit

**What the model suggested (subtly wrong):** “Check balance in Python after fetching credits/payouts into lists,” and “use `payout.status = 'failed'; payout.save()` inside the worker.”

**What was wrong:** Python-side sums drift under concurrency and are easy to get subtly inconsistent with what the DB sees. `save()` after a read allows **two workers** to both think they moved the same `processing` row.

**What we shipped instead:** **DB `Sum()` aggregates** inside the locked transaction for payout creation, and **guarded `QuerySet.update(...)`** for worker transitions, plus **`select_for_update(skip_locked=True)`** for claiming.
