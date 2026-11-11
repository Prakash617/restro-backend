from rest_framework import serializers
from .models import Branch


class BranchSerializer(serializers.ModelSerializer):
    tables_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = [
            "id",
            "name",
            "code",
            "slug",
            "is_main_branch",
            "address",
            "city",
            "phone",
            "email",
            "manager_name",
            "opening_time",
            "closing_time",
            "operating_hours_json",
            "holidays_json",
            "pan_vat_number",
            "tax_rate_percent",
            "service_charge_percent",
            "receipt_header",
            "receipt_footer",
            "is_active",
            "accepting_online_orders",
            "tables_count",
            "staff_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_tables_count(self, obj):
        try:
            return obj.tables.count()
        except Exception:
            return 0

    def get_staff_count(self, obj):
        try:
            return obj.staff_members.count()
        except Exception:
            return 0
