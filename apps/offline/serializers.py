from rest_framework import serializers

from .models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id",
            "client_uuid",
            "url",
            "kind",
            "content_type",
            "size",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        # Relative URL: the frontend resolves it against the media/backend origin.
        return obj.file.url if obj.file else ""
