import logging
import random
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Payout
from .state_machine import assert_legal_transition

logger = logging.getLogger(__name__)

BACKOFF_BASE_SECONDS = 30
MAX_BANK_ATTEMPTS = 3  # after 3 hangs, force failed


def _backoff_seconds(after_attempt: int) -> int:
    """Wait after attempt N (1-based) before the next bank simulation is allowed."""
    if after_attempt <= 0:
        return 0
    return int(BACKOFF_BASE_SECONDS * (2 ** (after_attempt - 1)))


def _bank_outcome() -> str:
    r = random.random()
    if r < 0.70:
        return "completed"
    if r < 0.90:
        return "failed"
    return "hang"


@shared_task
def claim_and_process_payouts() -> None:
    """Pick pending payouts (SKIP LOCKED), claim pending->processing, then simulate bank."""
    with transaction.atomic():
        candidates = list(
            Payout.objects.filter(status=Payout.Status.PENDING)
            .select_for_update(skip_locked=True)
            .order_by("id")[:25]
        )
        claimed_ids: list[int] = []
        now = timezone.now()
        for p in candidates:
            assert_legal_transition(Payout.Status.PENDING, Payout.Status.PROCESSING)
            updated = Payout.objects.filter(pk=p.pk, status=Payout.Status.PENDING).update(
                status=Payout.Status.PROCESSING,
                processing_started_at=now,
                attempt_count=0,
            )
            if updated:
                claimed_ids.append(p.pk)
    for pk in claimed_ids:
        simulate_bank_for_payout.delay(pk)


@shared_task
def retry_stuck_processing_payouts() -> None:
    """Re-run bank simulation for processing payouts past due (exponential backoff)."""
    qs = Payout.objects.filter(status=Payout.Status.PROCESSING).order_by("id")[:100]
    for p in qs:
        simulate_bank_for_payout.delay(p.pk)


@shared_task
def simulate_bank_for_payout(payout_id: int) -> None:
    with transaction.atomic():
        try:
            p = Payout.objects.select_for_update().get(pk=payout_id)
        except Payout.DoesNotExist:
            return

        if p.status != Payout.Status.PROCESSING:
            return

        now = timezone.now()
        if p.attempt_count > 0 and p.processing_started_at is not None:
            need = timedelta(seconds=_backoff_seconds(p.attempt_count))
            if now < p.processing_started_at + need:
                return

        next_attempt = p.attempt_count + 1
        outcome = _bank_outcome()

        if outcome == "completed":
            assert_legal_transition(Payout.Status.PROCESSING, Payout.Status.COMPLETED)
            updated = Payout.objects.filter(pk=p.pk, status=Payout.Status.PROCESSING).update(
                status=Payout.Status.COMPLETED,
                attempt_count=next_attempt,
                last_error="",
            )
            if updated == 0:
                logger.info("payout %s completed transition skipped (race)", payout_id)
            return

        if outcome == "failed":
            assert_legal_transition(Payout.Status.PROCESSING, Payout.Status.FAILED)
            updated = Payout.objects.filter(pk=p.pk, status=Payout.Status.PROCESSING).update(
                status=Payout.Status.FAILED,
                attempt_count=next_attempt,
                last_error="simulated_bank_failure",
            )
            if updated == 0:
                logger.info("payout %s failed transition skipped (race)", payout_id)
            return

        # hang
        if next_attempt >= MAX_BANK_ATTEMPTS:
            assert_legal_transition(Payout.Status.PROCESSING, Payout.Status.FAILED)
            updated = Payout.objects.filter(pk=p.pk, status=Payout.Status.PROCESSING).update(
                status=Payout.Status.FAILED,
                attempt_count=next_attempt,
                last_error="max_bank_attempts_exceeded",
            )
            if updated == 0:
                logger.info("payout %s max-attempt fail skipped (race)", payout_id)
            return

        updated = Payout.objects.filter(pk=p.pk, status=Payout.Status.PROCESSING).update(
            attempt_count=next_attempt,
            processing_started_at=now,
            last_error="simulated_processing_delay",
        )
        if updated == 0:
            logger.info("payout %s hang update skipped (race)", payout_id)
