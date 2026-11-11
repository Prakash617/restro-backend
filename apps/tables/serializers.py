from rest_framework import serializers
from .models import DiningTable, DiningZone


class DiningTableSerializer(serializers.ModelSerializer):
    zone_name = serializers.CharField(source="zone.name", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    merged_into_number = serializers.CharField(
        source="merged_into.table_number", read_only=True, default=""
    )
    merged_table_numbers = serializers.SerializerMethodField()
    active_order = serializers.SerializerMethodField()

    class Meta:
        model = DiningTable
        fields = [
            "id",
            "branch",
            "branch_name",
            "zone",
            "zone_name",
            "table_number",
            "capacity",
            "shape",
            "status",
            "merged_into",
            "merged_into_number",
            "merged_table_numbers",
            "current_guest_count",
            "qr_code_token",
            "pos_x",
            "pos_y",
            "notes",
            "active_order",
        ]
        read_only_fields = [
            "id",
            "zone_name",
            "branch_name",
            "merged_into_number",
            "merged_table_numbers",
            "active_order",
        ]

    def get_merged_table_numbers(self, obj):
        return list(obj.merged_tables.values_list("table_number", flat=True))

    def get_active_order(self, obj):
        try:
            order = (
                obj.orders.exclude(status__in=["COMPLETED", "CANCELLED"])
                .order_by("-created_at")
                .first()
            )
            if not order:
                return None
            return {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "total_amount": str(order.total_amount),
                "guest_count": order.guest_count,
                "waiter_name": order.waiter.full_name if order.waiter else "",
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }
        except Exception:
            return None


class DiningZoneSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True, default="")
    tables_count = serializers.SerializerMethodField()
    tables = DiningTableSerializer(many=True, read_only=True)

    class Meta:
        model = DiningZone
        fields = [
            "id",
            "branch",
            "branch_name",
            "name",
            "code",
            "floor_number",
            "is_active",
            "tables_count",
            "tables",
        ]
        read_only_fields = ["id", "branch_name", "tables_count", "tables"]

    def get_tables_count(self, obj):
        return obj.tables.count()
