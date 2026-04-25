from django.urls import path

from .views import BalanceView, CreditListView, PayoutsView

urlpatterns = [
    path("v1/balance/", BalanceView.as_view(), name="balance"),
    path("v1/credits/", CreditListView.as_view(), name="credits"),
    path("v1/payouts/", PayoutsView.as_view(), name="payouts"),
]
