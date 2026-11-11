from rest_framework import serializers
from .models import MenuCategory, MenuItem


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    profit_margin_percent = serializers.SerializerMethodField()
    recipe_items = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "slug",
            "sku",
            "description",
            "price",
            "cost_price",
            "profit_margin_percent",
            "prep_time_minutes",
            "kitchen_station",
            "is_vegetarian",
            "is_vegan",
            "is_gluten_free",
            "spice_level",
            "allergens_json",
            "calories",
            "image_url",
            "is_available",
            "is_featured",
            "variants_json",
            "modifiers_json",
            "recipe_items",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "category_name",
            "profit_margin_percent",
            "recipe_items",
            "created_at",
        ]

    def get_profit_margin_percent(self, obj):
        if obj.price and obj.price > 0:
            margin = ((obj.price - (obj.cost_price or 0)) / obj.price) * 100
            return round(float(margin), 1)
        return 0.0

    def get_recipe_items(self, obj):
        try:
            return [
                {
                    "id": r.id,
                    "inventory_item": r.inventory_item_id,
                    "inventory_item_name": r.inventory_item.name,
                    "unit": r.inventory_item.unit,
                    "quantity_required": str(r.quantity_required),
                    "unit_note": r.unit_note,
                }
                for r in obj.recipe_items.select_related("inventory_item").all()
            ]
        except Exception:
            return []


class MenuCategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, default=""
    )
    items_count = serializers.SerializerMethodField()
    items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = MenuCategory
        fields = [
            "id",
            "parent",
            "parent_name",
            "name",
            "slug",
            "description",
            "icon",
            "display_order",
            "available_from",
            "available_until",
            "is_active",
            "items_count",
            "items",
        ]
        read_only_fields = ["id", "parent_name", "items_count", "items"]

    def get_items_count(self, obj):
        return obj.items.count()
