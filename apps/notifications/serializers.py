from rest_framework import serializers
from .models import Notification, PushSubscription


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = [
            "id",
            "endpoint",
            "p256dh",
            "auth",
            "user_agent",
            "is_active",
            "created_at",
            "last_seen_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "last_seen_at"]
        extra_kwargs = {
            "endpoint": {"write_only": True},
            "p256dh": {"write_only": True},
            "auth": {"write_only": True},
        }


class NotificationSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "branch",
            "branch_name",
            "category",
            "severity",
            "title",
            "message",
            "action_url",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "branch_name", "created_at"]
