from rest_framework import serializers
from .models import TableReservation


class TableReservationSerializer(serializers.ModelSerializer):
    table_number = serializers.CharField(
        source="table.table_number", read_only=True, default=""
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )

    class Meta:
        model = TableReservation
        fields = [
            "id",
            "branch",
            "branch_name",
            "reservation_code",
            "customer",
            "guest_name",
            "guest_phone",
            "guest_email",
            "party_size",
            "reservation_date",
            "reservation_time",
            "duration_minutes",
            "table",
            "table_number",
            "status",
            "occasion",
            "special_requests",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "reservation_code",
            "table_number",
            "created_at",
        ]
