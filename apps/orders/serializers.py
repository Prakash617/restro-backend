from decimal import Decimal
from rest_framework import serializers
from apps.menu.models import MenuItem
from .models import Order, OrderItem, PaymentTransaction


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "order",
            "menu_item",
            "item_name",
            "variant_name",
            "kitchen_station",
            "course",
            "quantity",
            "unit_price",
            "line_total",
            "modifiers_json",
            "special_instructions",
            "kot_batch",
            "kot_status",
            "is_stock_deducted",
            "started_at",
            "ready_at",
        ]
        read_only_fields = ["id", "order", "line_total"]
        extra_kwargs = {
            "item_name": {"required": False},
            "unit_price": {"required": False},
        }

    def get_line_total(self, obj):
        return str(obj.line_total)


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "order",
            "amount",
            "method",
            "reference",
            "paid_by_label",
            "gateway_status",
            "created_at",
        ]
        read_only_fields = ["id", "order", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)
    payments = PaymentTransactionSerializer(many=True, read_only=True)
    table_number = serializers.CharField(
        source="table.table_number", read_only=True, default=""
    )
    waiter_name = serializers.CharField(
        source="waiter.full_name", read_only=True, default=""
    )
    cashier_name = serializers.CharField(
        source="cashier.full_name", read_only=True, default=""
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    taxable_amount = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "branch",
            "branch_name",
            "order_number",
            "order_type",
            "channel",
            "status",
            "payment_status",
            "payment_method",
            "table",
            "table_number",
            "waiter",
            "waiter_name",
            "cashier",
            "cashier_name",
            "customer",
            "customer_name",
            "customer_phone",
            "customer_address",
            "customer_pan",
            "guest_count",
            "coupon_code",
            "subtotal",
            "discount_amount",
            "service_charge",
            "taxable_amount",
            "tax_amount",
            "total_amount",
            "loyalty_points_earned",
            "loyalty_points_redeemed",
            "refund_amount",
            "refund_reason",
            "notes",
            "invoice_number",
            "items",
            "payments",
            "created_at",
            "updated_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "order_number",
            "table_number",
            "waiter_name",
            "cashier_name",
            "taxable_amount",
            "invoice_number",
            "payments",
            "created_at",
            "updated_at",
        ]

    def get_taxable_amount(self, obj):
        taxable = max(
            Decimal("0.00"),
            Decimal(str(obj.subtotal or "0.00"))
            - Decimal(str(obj.discount_amount or "0.00"))
            + Decimal(str(obj.service_charge or "0.00")),
        )
        return str(taxable.quantize(Decimal("0.01")))

    def get_invoice_number(self, obj):
        try:
            inv = obj.tax_invoice.first()
            return inv.invoice_number if inv else ""
        except Exception:
            return ""

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None) if request else None

        if request and request.user and request.user.is_authenticated and not validated_data.get("waiter"):
            validated_data["waiter"] = request.user

        order = Order.objects.create(**validated_data)

        for item_data in items_data:
            menu_item = item_data.get("menu_item")
            if isinstance(menu_item, int):
                menu_item = MenuItem.objects.filter(pk=menu_item).first()
            item_name = item_data.get("item_name") or (
                menu_item.name if menu_item else "Custom Item"
            )
            unit_price = item_data.get("unit_price")
            if unit_price is None:
                unit_price = menu_item.price if menu_item else Decimal("0.00")
            kitchen_station = item_data.get("kitchen_station") or (
                menu_item.kitchen_station if menu_item else "HOT_KITCHEN"
            )
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                item_name=item_name,
                variant_name=item_data.get("variant_name", ""),
                kitchen_station=kitchen_station,
                course=item_data.get("course", OrderItem.Course.MAIN),
                quantity=item_data.get("quantity", 1),
                unit_price=unit_price,
                modifiers_json=item_data.get("modifiers_json", []),
                special_instructions=item_data.get("special_instructions", ""),
                kot_batch=item_data.get("kot_batch", 1),
                kot_status=item_data.get("kot_status", OrderItem.KotStatus.QUEUED),
            )

        order.recalculate_totals(tenant=tenant)
        return order
