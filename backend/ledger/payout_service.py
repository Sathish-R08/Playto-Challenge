"""
POST /api/v1/payouts: one transaction.atomic() for the money + idempotency side.

Order inside the block (after acquiring the merchant row lock):
1. select_for_update() on merchant row
2. Idempotent replay: if idempotency row exists, return payout (or 422 if expired)
3. Compute available balance via DB aggregate
4. Check sufficient funds
5. get_or_create idempotency key (payout FK null until step 6 commits together)
6. Create payout row
7. Link idempotency to payout

All commit together or all roll back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import uuid

from django.db import transaction
from django.utils import timezone

from .balance import merchant_balance_aggregate
from .models import Merchant, Payout, PayoutIdempotency


IDEMPOTENCY_TTL = timezone.timedelta(hours=24)


@dataclass
class PayoutCreateResult:
    payout: Payout
    created: bool  # False when replaying idempotency


def _parse_uuid_key(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ValueError("missing key")
    uuid.UUID(s)  # merchant-supplied UUID per spec
    if len(s) > 64:
        raise ValueError("Idempotency-Key too long")
    return s


def create_payout_request(
    merchant: Merchant,
    idempotency_key: str,
    amount_paise: int,
    bank_account_id: str,
) -> Tuple[Optional[PayoutCreateResult], Optional[str]]:
    """
    Returns (result, error_code) where error_code is one of:
    idempotency_key_expired, insufficient_funds, invalid_key, invalid_amount
    or None on success.
    """
    try:
        key = _parse_uuid_key(idempotency_key)
    except ValueError:
        return (None, "invalid_key")

    if amount_paise <= 0:
        return (None, "invalid_amount")

    with transaction.atomic():
        # 1) Merchant row lock — serializes concurrent payout creates for this merchant.
        m = Merchant.objects.select_for_update().get(pk=merchant.pk)

        # 2) Idempotent replay (same lock; before balance check so retries never mis-classify funds).
        existing = (
            PayoutIdempotency.objects.select_related("payout")
            .filter(merchant=m, key=key)
            .first()
        )
        if existing is not None:
            if timezone.now() - existing.created_at > IDEMPOTENCY_TTL:
                return (None, "idempotency_key_expired")
            if existing.payout_id is None:
                return (None, "idempotency_incomplete")
            return (PayoutCreateResult(payout=existing.payout, created=False), None)

        # 3) DB-level aggregates only
        bal = merchant_balance_aggregate(m)
        available = bal["available_paise"]
        # 4) Sufficient funds
        if available < amount_paise:
            return (None, "insufficient_funds")

        # 5) Idempotency row then 6) payout — single commit (FK nullable only until row 6 exists).
        idem, _created = PayoutIdempotency.objects.get_or_create(
            merchant=m,
            key=key,
            defaults={"payout": None},
        )
        payout = Payout.objects.create(
            merchant=m,
            amount_paise=amount_paise,
            bank_account_id=bank_account_id,
            status=Payout.Status.PENDING,
        )
        idem.payout = payout
        idem.save(update_fields=["payout"])

        return (PayoutCreateResult(payout=payout, created=True), None)
