from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsRestaurantStaff
from .models import Coupon, Customer, CustomerFeedback, LoyaltyTransaction
from .serializers import (
    CouponSerializer,
    CustomerFeedbackSerializer,
    CustomerSerializer,
)


class CustomerListCreateView(generics.ListCreateAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [permissions.AllowAny]


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Customer.objects.prefetch_related("loyalty_transactions").all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.AllowAny]


class CustomerLookupView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        phone = (request.query_params.get("phone") or "").strip()
        if not phone:
            return Response(
                {"detail": "phone query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customer = (
            Customer.objects.prefetch_related("loyalty_transactions")
            .filter(phone__icontains=phone)
            .first()
        )
        if not customer:
            return Response(
                {"found": False, "customer": None},
                status=status.HTTP_200_OK,
            )
        return Response(
            {
                "found": True,
                "customer": CustomerSerializer(customer).data,
            },
            status=status.HTTP_200_OK,
        )


class CustomerAdjustPointsView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        customer = generics.get_object_or_404(Customer, pk=pk)
        points = int(request.data.get("points") or request.data.get("points_delta") or 0)
        tx_type = (
            request.data.get("transaction_type")
            or LoyaltyTransaction.TransactionType.ADJUSTMENT
        ).upper()
        description = (
            request.data.get("description")
            or request.data.get("reason")
            or "Manual loyalty points adjustment"
        )
        order_number = request.data.get("order_number") or ""

        if points == 0:
            return Response(
                {"detail": "Non-zero points value is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer.loyalty_points = max(0, customer.loyalty_points + points)
        if points > 0:
            customer.lifetime_points += points
        customer.recalculate_tier()
        customer.save(update_fields=["loyalty_points", "lifetime_points", "tier"])

        LoyaltyTransaction.objects.create(
            customer=customer,
            order_number=order_number,
            transaction_type=tx_type,
            points=points,
            description=description,
        )
        return Response(CustomerSerializer(customer).data, status=status.HTTP_200_OK)


class CouponListCreateView(generics.ListCreateAPIView):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.AllowAny]


class CouponDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Coupon.objects.all()
    serializer_class = CouponSerializer
    permission_classes = [permissions.AllowAny]


class CouponValidateView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = (request.data.get("code") or "").strip().upper()
        subtotal = Decimal(str(request.data.get("subtotal") or "0.00"))
        if not code:
            return Response(
                {"valid": False, "detail": "Coupon code is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        coupon = Coupon.objects.filter(code__iexact=code, is_active=True).first()
        if not coupon:
            return Response(
                {"valid": False, "detail": f"Coupon '{code}' is invalid or inactive."},
                status=status.HTTP_404_NOT_FOUND,
            )

        today = timezone.now().date()
        if coupon.valid_until and coupon.valid_until < today:
            return Response(
                {"valid": False, "detail": f"Coupon '{code}' has expired."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
            return Response(
                {"valid": False, "detail": f"Coupon '{code}' has reached its usage limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if subtotal > 0 and subtotal < coupon.min_order_amount:
            return Response(
                {
                    "valid": False,
                    "detail": f"Minimum order amount of {coupon.min_order_amount} required for coupon '{code}'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            calc_discount = (subtotal * coupon.discount_value) / Decimal("100.00")
            if coupon.max_discount_amount and coupon.max_discount_amount > 0:
                calc_discount = min(calc_discount, coupon.max_discount_amount)
        else:
            calc_discount = coupon.discount_value
            if subtotal > 0:
                calc_discount = min(calc_discount, subtotal)

        return Response(
            {
                "valid": True,
                "coupon": CouponSerializer(coupon).data,
                "discount_amount": str(round(calc_discount, 2)),
            },
            status=status.HTTP_200_OK,
        )


class CustomerFeedbackListCreateView(generics.ListCreateAPIView):
    queryset = CustomerFeedback.objects.select_related("customer").all()
    serializer_class = CustomerFeedbackSerializer
    permission_classes = [permissions.AllowAny]
