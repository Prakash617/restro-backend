from rest_framework import serializers
from .models import AuditLog, StaffShift, User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    role_display = serializers.CharField(source="get_role_display", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "role_display",
            "phone",
            "department",
            "specialization",
            "branch",
            "branch_name",
            "pos_pin",
            "permissions_json",
            "avatar_url",
            "is_public_staff",
            "is_active",
            "date_joined",
            "password",
        ]
        read_only_fields = ["id", "date_joined", "role_display", "branch_name"]

    def create(self, validated_data):
        password = validated_data.pop("password", None) or "Admin@12345"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class StaffShiftSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.full_name", read_only=True)
    staff_role = serializers.CharField(source="staff.role", read_only=True)
    staff_email = serializers.CharField(source="staff.email", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = StaffShift
        fields = [
            "id",
            "staff",
            "staff_name",
            "staff_role",
            "staff_email",
            "branch",
            "branch_name",
            "role_on_shift",
            "shift_date",
            "start_time",
            "end_time",
            "station",
            "status",
            "clock_in_at",
            "clock_out_at",
            "notes",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "staff_name",
            "staff_role",
            "staff_email",
            "branch_name",
            "created_at",
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor",
            "actor_name",
            "branch",
            "branch_name",
            "action",
            "target_model",
            "target_id",
            "description",
            "metadata_json",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "branch_name"]
