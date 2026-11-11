import json
import logging

from django.db import IntegrityError, connection, transaction
from django.http import JsonResponse

logger = logging.getLogger(__name__)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SKIPPED_PREFIXES = (
    "/api/v1/auth/",
    "/api/v1/public/",
    "/api/v1/superadmin/",
)
MAX_CACHED_BODY_BYTES = 64 * 1024


def _bearer_token(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header:
        return ""
    parts = header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return ""
    return parts[1].strip()


def _resolve_user_id(request):
    """
    Resolve the acting user *before* DRF authentication runs.

    Django's ``AuthenticationMiddleware`` only knows about session users, and
    this platform authenticates with JWTs that DRF validates later inside the
    view. Without resolving the JWT here the middleware would never see an
    authenticated user and idempotency replay would silently never happen.

    Returns ``(user_id, authenticated)``. The JWT is only *decoded* (signature
    and expiry are validated by SimpleJWT); the tenant binding check stays in
    ``TenantBoundJWTAuthentication`` so it is not duplicated here.
    """
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        return getattr(user, "pk", None), True

    token = _bearer_token(request)
    if not token:
        return None, False

    try:
        from rest_framework_simplejwt.tokens import AccessToken

        validated = AccessToken(token)
    except Exception:
        # An invalid/expired token will be rejected by DRF with a 401. The
        # middleware simply does not cache anything for that request.
        return None, False

    user_id = validated.payload.get("user_id")
    if user_id is None:
        return None, False
    try:
        return int(user_id), True
    except (TypeError, ValueError):
        return None, False


class IdempotencyMiddleware:
    """
    Replays successful mutating responses for a tenant/user when the client
    retries with the same ``Idempotency-Key``.

    Security notes:
    - Only tenant-schema requests are handled (superadmin/public auth responses
      are never stored).
    - Keys are bound to the authenticated user and request path, so a leaked
      key cannot be replayed against another endpoint or account.
    - The middleware fails open if the table is not migrated yet, so the API
      keeps working during rolling deployments.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        key = (
            request.headers.get("Idempotency-Key")
            or request.headers.get("X-Idempotency-Key")
            or ""
        ).strip()
        should_handle = (
            request.method in MUTATING_METHODS
            and bool(key)
            and len(key) <= 128
            and request.path.startswith("/api/")
            and getattr(connection, "schema_name", "public") != "public"
            and not any(request.path.startswith(prefix) for prefix in SKIPPED_PREFIXES)
        )

        if not should_handle:
            return self.get_response(request)

        user_id, authenticated = _resolve_user_id(request)
        if not authenticated:
            # Unauthenticated mutations are handled by DRF's permission layer.
            return self.get_response(request)

        from apps.offline.models import IdempotencyRecord

        try:
            existing = IdempotencyRecord.objects.filter(key=key).first()
        except Exception:  # table missing / database unavailable -> fail open
            logger.warning("Idempotency lookup skipped for %s", request.path, exc_info=True)
            return self.get_response(request)

        if existing is not None:
            if (
                existing.user_id != user_id
                or existing.method != request.method
                or existing.path != request.path
            ):
                return JsonResponse(
                    {
                        "code": "IDEMPOTENCY_KEY_REUSED",
                        "detail": (
                            "This Idempotency-Key was already used for a different "
                            "operation. Generate a new key for this request."
                        ),
                    },
                    status=409,
                )

            response = JsonResponse(existing.response_body, safe=False, status=existing.status_code)
            response["Idempotent-Replay"] = "true"
            response["Cache-Control"] = "no-store"
            return response

        response = self.get_response(request)

        if not (200 <= response.status_code < 300) or getattr(response, "streaming", False):
            return response

        content_type = response.get("Content-Type", "")
        if "application/json" not in content_type:
            return response

        try:
            raw = response.content
        except Exception:
            return response

        if len(raw) > MAX_CACHED_BODY_BYTES:
            return response

        try:
            body = json.loads(raw.decode(response.charset or "utf-8"))
        except Exception:
            return response

        try:
            with transaction.atomic():
                IdempotencyRecord.objects.create(
                    key=key,
                    user_id=user_id,
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    response_body=body,
                )
        except IntegrityError:
            # Another worker stored the same key first. Its response is equally valid.
            pass
        except Exception:
            logger.warning("Idempotency store skipped for %s", request.path, exc_info=True)

        response["Cache-Control"] = "no-store"
        return response
