from django.contrib import admin

from .models import Credit, Merchant, Payout, PayoutIdempotency


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "api_token", "created_at")


@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "amount_paise", "created_at")


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "amount_paise", "status", "attempt_count", "created_at")


@admin.register(PayoutIdempotency)
class PayoutIdempotencyAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "key", "payout", "created_at")
