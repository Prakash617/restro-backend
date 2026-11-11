from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .push import send_push_to_user


@receiver(post_save, sender=Notification)
def push_operational_notification(sender, instance, created, **kwargs):
    """
    Forward new operational notifications to Web Push when enabled.

    Sending is opt-in via PUSH_NOTIFICATIONS_ENABLED and is a no-op unless both
    VAPID keys are configured. It runs after commit so a push failure can never
    roll back a POS/KDS transaction.
    """
    if not created or not getattr(settings, "PUSH_NOTIFICATIONS_ENABLED", False):
        return
    if getattr(instance, "recipient_id", None):
        recipients = [instance.recipient]
    else:
        from django.contrib.auth import get_user_model

        recipients = list(
            get_user_model().objects.filter(
                is_active=True,
                role__in=["TENANT_ADMIN", "MANAGER", "SUPER_ADMIN", "SUPERADMIN"],
            )
        )
    if not recipients:
        return

    def _dispatch():
        for user in recipients:
            send_push_to_user(
                user,
                title=instance.title,
                body=instance.message[:180],
                url=instance.action_url or "/dashboard",
                tag=f"notification-{instance.pk}",
            )

    transaction.on_commit(_dispatch)
