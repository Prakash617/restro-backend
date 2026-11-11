from rest_framework import serializers
from .models import Client, SubscriptionInvoice, SubscriptionPlan
from .services import get_tenant_live_metrics


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    code = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id",
            "name",
            "slug",
            "code",
            "description",
            "price_monthly",
            "price_yearly",
            "price_monthly_npr",
            "price_yearly_npr",
            "trial_days",
            "max_branches",
            "max_staff_users",
            "max_tables",
            "max_menu_items",
            "max_monthly_orders",
            "enable_pos",
            "enable_kds",
            "enable_inventory",
            "enable_online_ordering",
            "enable_table_reservations",
            "enable_loyalty_crm",
            "enable_multi_branch",
            "enable_advanced_analytics",
            "enable_custom_domain",
            "features_json",
            "is_active",
            "is_featured",
        ]
        read_only_fields = ["id", "code"]

    def get_code(self, obj):
        return obj.slug.upper()


class ClientSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(
        source="plan.name", read_only=True, default="Enterprise"
    )
    plan_slug = serializers.CharField(
        source="plan.slug", read_only=True, default="enterprise"
    )
    primary_domain = serializers.SerializerMethodField()
    branches_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    tables_count = serializers.SerializerMethodField()
    menu_items_count = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()
    gmv_revenue = serializers.SerializerMethodField()
    theme_id = serializers.SerializerMethodField()
    color_palette = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id",
            "schema_name",
            "name",
            "slug",
            "plan",
            "plan_name",
            "plan_slug",
            "subscription_status",
            "trial_ends_at",
            "is_active",
            "owner_name",
            "owner_email",
            "phone",
            "city",
            "country",
            "cuisine_type",
            "currency",
            "pan_vat_number",
            "tax_system",
            "tax_rate_percent",
            "is_tax_inclusive",
            "service_charge_percent",
            "fiscal_year",
            "logo_url",
            "primary_domain",
            "branches_count",
            "staff_count",
            "tables_count",
            "menu_items_count",
            "orders_count",
            "gmv_revenue",
            "theme_id",
            "color_palette",
            "created_on",
        ]
        read_only_fields = [
            "id",
            "schema_name",
            "plan_name",
            "plan_slug",
            "primary_domain",
            "branches_count",
            "staff_count",
            "tables_count",
            "menu_items_count",
            "orders_count",
            "gmv_revenue",
            "theme_id",
            "color_palette",
            "created_on",
        ]

    def _metrics(self, obj):
        cache_attr = f"_metrics_cache_{obj.id}"
        if not hasattr(self, cache_attr):
            setattr(self, cache_attr, get_tenant_live_metrics(obj))
        return getattr(self, cache_attr)

    def get_primary_domain(self, obj):
        dom = obj.domains.filter(is_primary=True).first() or obj.domains.first()
        return dom.domain if dom else f"{obj.slug}.localhost"

    def get_branches_count(self, obj):
        return self._metrics(obj)["branches_count"]

    def get_staff_count(self, obj):
        return self._metrics(obj)["staff_count"]

    def get_tables_count(self, obj):
        return self._metrics(obj)["tables_count"]

    def get_menu_items_count(self, obj):
        return self._metrics(obj)["menu_items_count"]

    def get_orders_count(self, obj):
        return self._metrics(obj)["orders_count"]

    def get_gmv_revenue(self, obj):
        return self._metrics(obj)["gmv_revenue"]

    def get_theme_id(self, obj):
        return self._metrics(obj)["theme_id"]

    def get_color_palette(self, obj):
        return self._metrics(obj)["color_palette"]


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    plan_name = serializers.CharField(
        source="plan.name", read_only=True, default="Enterprise"
    )

    class Meta:
        model = SubscriptionInvoice
        fields = [
            "id",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "plan",
            "plan_name",
            "invoice_number",
            "billing_cycle",
            "amount",
            "currency",
            "payment_gateway",
            "status",
            "period_start",
            "period_end",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "tenant_name",
            "tenant_slug",
            "plan_name",
            "created_at",
        ]
