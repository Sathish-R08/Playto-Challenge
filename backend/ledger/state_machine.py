from django.core.exceptions import ValidationError

from .models import Payout


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
