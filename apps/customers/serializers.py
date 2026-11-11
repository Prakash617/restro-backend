from rest_framework import serializers
from .models import Coupon, Customer, CustomerFeedback, LoyaltyTransaction


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoyaltyTransaction
        fields = [
            "id",
            "customer",
            "order_number",
            "transaction_type",
            "points",
            "description",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CustomerSerializer(serializers.ModelSerializer):
    recent_transactions = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "tier",
            "loyalty_points",
            "lifetime_points",
            "total_spent",
            "visits_count",
            "dietary_notes",
            "birthday",
            "is_active",
            "recent_transactions",
            "created_at",
        ]
        read_only_fields = ["id", "recent_transactions", "created_at"]

    def get_recent_transactions(self, obj):
        return LoyaltyTransactionSerializer(
            obj.loyalty_transactions.all()[:10], many=True
        ).data


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = [
            "id",
            "code",
            "title",
            "discount_type",
            "discount_value",
            "min_order_amount",
            "max_discount_amount",
            "valid_from",
            "valid_until",
            "usage_limit",
            "used_count",
            "is_active",
        ]
        read_only_fields = ["id"]


class CustomerFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerFeedback
        fields = [
            "id",
            "customer",
            "guest_name",
            "order_number",
            "food_rating",
            "service_rating",
            "ambience_rating",
            "overall_rating",
            "comment",
            "is_public",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
