import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.conf import settings
from django.db import connections
from rest_framework.test import APIClient

from ledger.models import Credit, Merchant, Payout, PayoutIdempotency


@pytest.mark.skipif(
    "sqlite" in settings.DATABASES["default"]["ENGINE"],
    reason="Threaded concurrency + row locks: run with DATABASE_URL=postgresql://... (see README).",
)
@pytest.mark.django_db(transaction=True)
def test_concurrent_payouts_only_one_succeeds_when_insufficient_aggregate():
    """
    Merchant has 10_000 paise available; two simultaneous 6_000 paise payouts
    must not both succeed (row-level merchant lock + DB aggregate check).
    """
    m = Merchant.objects.create(name="C1", api_token="tok-concurrency")
    Credit.objects.create(merchant=m, amount_paise=10_000, description="seed")

    url = "/api/v1/payouts/"
    headers = {"HTTP_AUTHORIZATION": "Bearer tok-concurrency"}

    def attempt():
        connections.close_all()
        client = APIClient()
        key = str(uuid.uuid4())
        return client.post(
            url,
            {"amount_paise": 6_000, "bank_account_id": "acct-1"},
            format="json",
            **headers,
            HTTP_IDEMPOTENCY_KEY=key,
        )

    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(attempt)
        f2 = ex.submit(attempt)
        codes = [f1.result().status_code, f2.result().status_code]

    assert sum(c in (200, 201) for c in codes) == 1
    assert sum(c == 400 for c in codes) == 1

    assert Payout.objects.filter(merchant=m).count() == 1
    assert PayoutIdempotency.objects.filter(merchant=m).count() == 1


@pytest.mark.django_db
def test_idempotency_returns_same_payout_without_duplicate():
    m = Merchant.objects.create(name="I1", api_token="tok-idem")
    Credit.objects.create(merchant=m, amount_paise=50_000, description="seed")

    client = APIClient()
    key = str(uuid.uuid4())
    url = "/api/v1/payouts/"
    headers = {"HTTP_AUTHORIZATION": "Bearer tok-idem", "HTTP_IDEMPOTENCY_KEY": key}
    body = {"amount_paise": 1_000, "bank_account_id": "acct-x"}

    r1 = client.post(url, body, format="json", **headers)
    r2 = client.post(url, body, format="json", **headers)

    assert r1.status_code in (200, 201)
    assert r2.status_code == 200
    assert r1.data["id"] == r2.data["id"]
    assert Payout.objects.filter(merchant=m).count() == 1
    assert PayoutIdempotency.objects.filter(merchant=m, key=key).count() == 1
