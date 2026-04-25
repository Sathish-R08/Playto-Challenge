from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import BearerTokenAuthentication, MerchantPrincipal
from .balance import merchant_balance_aggregate
from .models import Credit, Payout
from .payout_service import create_payout_request
from .serializers import CreditSerializer, PayoutRequestSerializer, PayoutSerializer


def _merchant(request) -> MerchantPrincipal:
    return request.user  # type: ignore[return-value]


class BalanceView(APIView):
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        m = _merchant(request).merchant
        return Response(merchant_balance_aggregate(m))


class CreditListView(APIView):
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        m = _merchant(request).merchant
        qs = Credit.objects.filter(merchant=m)[:50]
        return Response(CreditSerializer(qs, many=True).data)


class PayoutsView(APIView):
    authentication_classes = [BearerTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        m = _merchant(request).merchant
        qs = Payout.objects.filter(merchant=m)[:100]
        return Response(PayoutSerializer(qs, many=True).data)

    def post(self, request):
        body = PayoutRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)

        idem_key = request.headers.get("Idempotency-Key")
        if not idem_key:
            return Response(
                {"detail": "Idempotency-Key header is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result, err = create_payout_request(
            merchant=_merchant(request).merchant,
            idempotency_key=idem_key,
            amount_paise=body.validated_data["amount_paise"],
            bank_account_id=body.validated_data["bank_account_id"],
        )

        if err == "idempotency_key_expired":
            return Response(
                {
                    "code": "idempotency_key_expired",
                    "detail": "This Idempotency-Key is older than 24 hours; use a new key.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if err == "insufficient_funds":
            return Response(
                {"code": "insufficient_funds", "detail": "Not enough available balance for this payout."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if err in ("invalid_key", "invalid_amount"):
            return Response(
                {"code": err, "detail": "Invalid request."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if err == "idempotency_incomplete":
            return Response(
                {"code": "idempotency_incomplete", "detail": "Try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        assert result is not None

        code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return Response(PayoutSerializer(result.payout).data, status=code)
