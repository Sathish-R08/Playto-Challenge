from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed

from .models import Merchant


class MerchantPrincipal:
    """Minimal principal for DRF IsAuthenticated."""

    is_authenticated = True

    def __init__(self, merchant: Merchant):
        self.merchant = merchant


class BearerTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None
        token = header[7:].strip()
        if not token:
            raise AuthenticationFailed("Missing bearer token")
        try:
            merchant = Merchant.objects.get(api_token=token)
        except Merchant.DoesNotExist as exc:
            raise AuthenticationFailed("Invalid bearer token") from exc
        return (MerchantPrincipal(merchant), None)
