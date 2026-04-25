"""
Balance math in the database only (BigInteger sums).

available = Sum(credits) - Sum(payouts where status in pending, processing, completed)
held = Sum(payouts where status in pending, processing)
"""

from django.db.models import Sum
from django.db.models.functions import Coalesce

from .models import Credit, Payout, Merchant


def merchant_balance_aggregate(merchant: Merchant):
    """
    Returns dict with keys: credits_paise, outstanding_paise, held_paise, available_paise.
    All values are int (0 if null).
    """
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
    return {
        "credits_paise": int(credits),
        "outstanding_paise": int(outstanding),
        "held_paise": int(held),
        "available_paise": int(available),
    }
