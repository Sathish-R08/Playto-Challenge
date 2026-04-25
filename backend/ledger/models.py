from django.db import models


class Merchant(models.Model):
    name = models.CharField(max_length=255)
    api_token = models.CharField(max_length=128, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class Credit(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="credits")
    amount_paise = models.BigIntegerField()
    description = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="payouts")
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class PayoutIdempotency(models.Model):
    """
    payout may be null only for the duration of a single transaction before the
    Payout row is created; at commit time both rows exist (see service layer).
    """

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name="payout_idempotency_keys")
    key = models.CharField(max_length=64)
    payout = models.ForeignKey(
        Payout,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="idempotency_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["merchant", "key"], name="uniq_payout_idempotency_merchant_key"),
        ]
