from rest_framework import serializers

from .models import Credit, Payout


class PayoutRequestSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)


class PayoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = (
            "id",
            "amount_paise",
            "bank_account_id",
            "status",
            "attempt_count",
            "last_error",
            "processing_started_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CreditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credit
        fields = ("id", "amount_paise", "description", "created_at")
