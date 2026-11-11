from decimal import Decimal
from rest_framework import serializers
from .models import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    RecipeIngredient,
    StockMovement,
    Supplier,
)


class SupplierSerializer(serializers.ModelSerializer):
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "pan_number",
            "category",
            "is_active",
            "items_count",
            "created_at",
        ]
        read_only_fields = ["id", "items_count", "created_at"]

    def get_items_count(self, obj):
        return obj.items.count()


class InventoryItemSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source="supplier.name", read_only=True, default=""
    )
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    is_low_stock = serializers.BooleanField(read_only=True)
    stock_value = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = [
            "id",
            "branch",
            "branch_name",
            "sku",
            "name",
            "category",
            "unit",
            "current_stock",
            "reorder_level",
            "cost_per_unit",
            "stock_value",
            "supplier",
            "supplier_name",
            "is_low_stock",
            "last_restocked_at",
        ]
        read_only_fields = [
            "id",
            "branch_name",
            "supplier_name",
            "is_low_stock",
            "stock_value",
        ]

    def get_stock_value(self, obj):
        val = (obj.current_stock or Decimal("0")) * (obj.cost_per_unit or Decimal("0"))
        return str(round(val, 2))


class RecipeIngredientSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)
    inventory_item_name = serializers.CharField(
        source="inventory_item.name", read_only=True
    )
    unit = serializers.CharField(source="inventory_item.unit", read_only=True)
    cost_per_unit = serializers.DecimalField(
        source="inventory_item.cost_per_unit",
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = RecipeIngredient
        fields = [
            "id",
            "menu_item",
            "menu_item_name",
            "inventory_item",
            "inventory_item_name",
            "unit",
            "cost_per_unit",
            "quantity_required",
            "unit_note",
        ]
        read_only_fields = [
            "id",
            "menu_item_name",
            "inventory_item_name",
            "unit",
            "cost_per_unit",
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source="item.name", read_only=True)
    item_unit = serializers.CharField(source="item.unit", read_only=True)
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    performed_by_name = serializers.CharField(
        source="performed_by.full_name", read_only=True, default="System"
    )

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "item",
            "item_name",
            "item_unit",
            "branch",
            "branch_name",
            "movement_type",
            "quantity",
            "reason",
            "reference",
            "performed_by",
            "performed_by_name",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "item_name",
            "item_unit",
            "branch_name",
            "performed_by_name",
            "created_at",
        ]


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    inventory_item_name = serializers.CharField(
        source="inventory_item.name", read_only=True
    )
    unit = serializers.CharField(source="inventory_item.unit", read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id",
            "inventory_item",
            "inventory_item_name",
            "unit",
            "quantity_ordered",
            "quantity_received",
            "unit_cost",
        ]
        read_only_fields = ["id", "inventory_item_name", "unit"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    branch_name = serializers.CharField(
        source="branch.name", read_only=True, default=""
    )
    items = PurchaseOrderItemSerializer(many=True, required=False)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "branch",
            "branch_name",
            "po_number",
            "supplier",
            "supplier_name",
            "status",
            "total_amount",
            "expected_date",
            "notes",
            "items",
            "received_at",
            "created_at",
        ]
        read_only_fields = ["id", "branch_name", "supplier_name", "created_at"]
        extra_kwargs = {"po_number": {"required": False}}

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        po = PurchaseOrder.objects.create(**validated_data)
        total = Decimal("0.00")
        for item_data in items_data:
            inv_item = item_data["inventory_item"]
            qty = item_data.get("quantity_ordered", Decimal("1.000"))
            cost = item_data.get("unit_cost") or inv_item.cost_per_unit
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                inventory_item=inv_item,
                quantity_ordered=qty,
                quantity_received=item_data.get("quantity_received", Decimal("0.000")),
                unit_cost=cost,
            )
            total += qty * cost
        if total > 0 and not validated_data.get("total_amount"):
            po.total_amount = round(total, 2)
            po.save(update_fields=["total_amount"])
        return po
