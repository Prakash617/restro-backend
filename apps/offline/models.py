import os
import uuid

from django.conf import settings
from django.db import connection, models
from django.utils import timezone


def attachment_upload_path(instance, filename):
    """Store tenant uploads in isolated folders and never trust the client name."""
    schema = getattr(connection, "schema_name", "public") or "public"
    extension = os.path.splitext(filename or "")[1].lower()[:10]
    if not extension or not extension.startswith("."):
        extension = ".bin"
    return f"uploads/{schema}/{instance.client_uuid}{extension}"


class IdempotencyRecord(models.Model):
    """
    Tenant-scoped replay record for mutating API requests that carry an
    ``Idempotency-Key`` header. This prevents duplicate orders, stock
    adjustments and other queued offline operations from being applied twice
    when a client retries after a timeout.
    """

    key = models.CharField(max_length=128, unique=True)
    user_id = models.BigIntegerField(null=True, blank=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    status_code = models.PositiveIntegerField(default=200)
    response_body = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Idempotency record"
        verbose_name_plural = "Idempotency records"

    def __str__(self):
        return f"{self.method} {self.path} [{self.key[:12]}]"


class Attachment(models.Model):
    """
    Offline upload queue destination. ``client_uuid`` is generated on the
    device before the upload starts, making retries and duplicate submissions
    safe (the same UUID returns the same stored file).
    """

    class Kind(models.TextChoices):
        IMAGE = "IMAGE", "Image"
        DOCUMENT = "DOCUMENT", "Document"
        OTHER = "OTHER", "Other"

    client_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    file = models.FileField(upload_to=attachment_upload_path, max_length=500)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.IMAGE)
    content_type = models.CharField(max_length=120, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="offline_attachments",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.kind} {self.client_uuid}"
