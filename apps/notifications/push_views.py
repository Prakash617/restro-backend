from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsRestaurantStaff

from .models import PushSubscription
from .push import push_is_configured, send_push_to_user


def _is_tenant_schema():
    return getattr(connection, "schema_name", "public") != "public"


def _platform_unavailable():
    return Response(
        {
            "code": "PUSH_TENANT_ONLY",
            "detail": "Web Push subscriptions are stored per restaurant tenant.",
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


class PushVapidPublicKeyView(APIView):
    """Public VAPID identity. The private key is never serialized or exposed."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "configured": push_is_configured(),
                "publicKey": getattr(settings, "VAPID_PUBLIC_KEY", ""),
                "subject": getattr(settings, "VAPID_SUBJECT", ""),
            }
        )


class PushSubscribeView(APIView):
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        if not _is_tenant_schema():
            return _platform_unavailable()

        endpoint = (request.data.get("endpoint") or "").strip()
        keys = request.data.get("keys") or {}
        p256dh = (keys.get("p256dh") or request.data.get("p256dh") or "").strip()
        auth = (keys.get("auth") or request.data.get("auth") or "").strip()

        if not endpoint or not p256dh or not auth:
            return Response(
                {
                    "code": "INVALID_SUBSCRIPTION",
                    "detail": "endpoint and keys.p256dh / keys.auth are required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": (request.headers.get("User-Agent") or "")[:300],
                "is_active": True,
            },
        )
        return Response(
            {
                "subscribed": True,
                "created": created,
                "id": subscription.id,
                "configured": push_is_configured(),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class PushUnsubscribeView(APIView):
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        if not _is_tenant_schema():
            return _platform_unavailable()

        endpoint = (request.data.get("endpoint") or "").strip()
        if not endpoint:
            return Response(
                {"code": "ENDPOINT_REQUIRED", "detail": "endpoint is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted, _ = PushSubscription.objects.filter(
            endpoint=endpoint, user=request.user
        ).delete()
        return Response({"subscribed": False, "deleted": deleted})


class PushStatusView(APIView):
    permission_classes = [IsRestaurantStaff]

    def get(self, request):
        if not _is_tenant_schema():
            return _platform_unavailable()
        subscriptions = PushSubscription.objects.filter(user=request.user)
        return Response(
            {
                "configured": push_is_configured(),
                "supported": push_is_configured(),
                "count": subscriptions.filter(is_active=True).count(),
                "endpoints": [
                    {"id": s.id, "user_agent": s.user_agent, "last_seen_at": s.last_seen_at}
                    for s in subscriptions.filter(is_active=True)[:10]
                ],
            }
        )


class PushTestView(APIView):
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        if not _is_tenant_schema():
            return _platform_unavailable()
        if not push_is_configured():
            return Response(
                {
                    "code": "PUSH_NOT_CONFIGURED",
                    "detail": "VAPID keys are not configured on the server.",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        sent = send_push_to_user(
            request.user,
            title="RestoCloud notifications enabled",
            body="Operational alerts will now arrive on this device.",
            url=(request.data.get("url") or "/dashboard"),
            tag="restosaas-test",
        )
        return Response({"sent": sent})
