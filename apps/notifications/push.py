import json
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def push_is_configured():
    return bool(
        getattr(settings, "VAPID_PRIVATE_KEY", "")
        and getattr(settings, "VAPID_PUBLIC_KEY", "")
    )


def _send_to_subscription(subscription, payload):
    from pywebpush import WebPushException, webpush

    return webpush(
        subscription_info={
            "endpoint": subscription.endpoint,
            "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
        },
        data=json.dumps(payload),
        vapid_private_key=settings.VAPID_PRIVATE_KEY,
        vapid_claims={"sub": settings.VAPID_SUBJECT},
        timeout=10,
    )


def send_push_to_user(user, *, title, body, url="/dashboard", tag=None):
    """
    Sends a Web Push message to every active subscription for ``user``.

    Returns the number of successful deliveries. Expired subscriptions
    (HTTP 404/410) are deactivated automatically. If VAPID keys or pywebpush
    are unavailable, this function is a safe no-op so business flows never fail.
    """
    if not push_is_configured() or user is None:
        return 0

    from pywebpush import WebPushException

    from .models import PushSubscription

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "tag": tag or "restosaas",
        "timestamp": timezone.now().isoformat(),
    }

    sent = 0
    for subscription in PushSubscription.objects.filter(user=user, is_active=True):
        try:
            _send_to_subscription(subscription, payload)
            sent += 1
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code in (404, 410):
                subscription.is_active = False
                subscription.save(update_fields=["is_active"])
            else:
                logger.warning("Web push failed for subscription %s: %s", subscription.pk, exc)
        except Exception:
            logger.warning("Web push unexpected failure for subscription %s", subscription.pk, exc_info=True)
    return sent


def send_push_to_user_ids(user_ids, *, title, body, url="/dashboard", tag=None):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    total = 0
    for user in User.objects.filter(pk__in=user_ids, is_active=True):
        total += send_push_to_user(user, title=title, body=body, url=url, tag=tag)
    return total
