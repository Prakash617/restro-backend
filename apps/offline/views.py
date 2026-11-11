import uuid

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsRestaurantStaff

from .models import Attachment
from .serializers import AttachmentSerializer

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/heic",
    "image/heif",
    "application/pdf",
}


class AttachmentUploadView(APIView):
    """
    Upload endpoint used by the offline upload queue.

    The device generates ``client_uuid`` before uploading. Retrying the same
    UUID returns the previously stored file instead of creating a duplicate.
    """

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsRestaurantStaff]

    def post(self, request):
        raw_uuid = request.data.get("client_uuid") or ""
        try:
            client_uuid = uuid.UUID(str(raw_uuid))
        except (ValueError, AttributeError, TypeError):
            return Response(
                {
                    "code": "INVALID_CLIENT_UUID",
                    "detail": "A valid client_uuid is required for idempotent uploads.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = Attachment.objects.filter(client_uuid=client_uuid).first()
        if existing is not None:
            if existing.uploaded_by_id not in (None, request.user.id):
                return Response(
                    {
                        "code": "UPLOAD_CONFLICT",
                        "detail": "This upload UUID belongs to another user.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                AttachmentSerializer(existing, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )

        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"code": "FILE_REQUIRED", "detail": "A file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if upload.size > MAX_UPLOAD_BYTES:
            return Response(
                {
                    "code": "FILE_TOO_LARGE",
                    "detail": "Files must be 10 MB or smaller.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        content_type = (getattr(upload, "content_type", "") or "").lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            return Response(
                {
                    "code": "UNSUPPORTED_FILE_TYPE",
                    "detail": f"Unsupported file type: {content_type or 'unknown'}.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        kind = request.data.get("kind") or (
            Attachment.Kind.DOCUMENT if content_type == "application/pdf" else Attachment.Kind.IMAGE
        )
        if kind not in Attachment.Kind.values:
            kind = Attachment.Kind.OTHER

        attachment = Attachment.objects.create(
            client_uuid=client_uuid,
            file=upload,
            kind=kind,
            content_type=content_type,
            size=upload.size,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        return Response(
            AttachmentSerializer(attachment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
