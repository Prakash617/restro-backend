from decimal import Decimal
from django_tenants.utils import schema_context
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, User
from apps.accounts.permissions import IsRestaurantStaff
from apps.accounts.serializers import UserSerializer
from apps.accounts.views import build_tenant_summary
from apps.branches.models import Branch
from apps.branches.serializers import BranchSerializer
from apps.customers.models import Coupon, Customer, CustomerFeedback
from apps.customers.serializers import CouponSerializer, CustomerFeedbackSerializer
from apps.menu.models import MenuCategory, MenuItem
from apps.menu.serializers import MenuCategorySerializer, MenuItemSerializer
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem
from apps.orders.serializers import OrderSerializer
from apps.reservations.models import TableReservation
from apps.reservations.serializers import TableReservationSerializer
from apps.tables.models import DiningTable
from apps.tenants.models import Client
from .models import RestaurantWebsiteSettings, Testimonial
from .serializers import RestaurantWebsiteSettingsSerializer, TestimonialSerializer


def _get_or_create_website_settings():
    settings_obj = RestaurantWebsiteSettings.objects.first()
    if not settings_obj:
        settings_obj = RestaurantWebsiteSettings.objects.create()
    return settings_obj


class WebsiteSettingsRetrieveUpdateView(APIView):
    permission_classes = [IsRestaurantStaff]

    def get(self, request):
        settings_obj = _get_or_create_website_settings()
        return Response(
            RestaurantWebsiteSettingsSerializer(settings_obj).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        settings_obj = _get_or_create_website_settings()
        serializer = RestaurantWebsiteSettingsSerializer(
            settings_obj, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        AuditLog.objects.create(
            actor=request.user if request.user.is_authenticated else None,
            actor_name=getattr(request.user, "full_name", "Admin"),
            action=AuditLog.Action.SETTINGS_UPDATED,
            target_model="RestaurantWebsiteSettings",
            target_id=str(settings_obj.id),
            description=f"Updated website theme/settings ({settings_obj.theme_id}, {settings_obj.color_palette}).",
            metadata_json={
                "theme_id": settings_obj.theme_id,
                "color_palette": settings_obj.color_palette,
            },
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        return self.patch(request)


class TestimonialListCreateView(generics.ListCreateAPIView):
    queryset = Testimonial.objects.all()
    serializer_class = TestimonialSerializer
    permission_classes = [IsRestaurantStaff]


class TestimonialDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Testimonial.objects.all()
    serializer_class = TestimonialSerializer
    permission_classes = [IsRestaurantStaff]


def _resolve_public_tenant(tenant_slug):
    with schema_context("public"):
        return (
            Client.objects.select_related("plan")
            .filter(slug__iexact=tenant_slug)
            .first()
        )


class PublicRestaurantSiteView(APIView):
    """Returns full public website payload for a restaurant tenant."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, tenant_slug):
        tenant = _resolve_public_tenant(tenant_slug)
        if not tenant or tenant.schema_name == "public":
            return Response(
                {"detail": f"Restaurant '{tenant_slug}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not tenant.is_active or tenant.subscription_status == "SUSPENDED":
            return Response(
                {
                    "code": "TENANT_SUSPENDED",
                    "detail": f"{tenant.name} is currently unavailable.",
                    "tenant": tenant.name,
                    "tenant_name": tenant.name,
                    "tenant_slug": tenant.slug,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        tenant_summary = build_tenant_summary(tenant)

        with schema_context(tenant.schema_name):
            settings_obj = _get_or_create_website_settings()
            branches = BranchSerializer(
                Branch.objects.filter(is_active=True), many=True
            ).data
            categories = MenuCategorySerializer(
                MenuCategory.objects.filter(is_active=True).prefetch_related("items"),
                many=True,
            ).data
            available_items = MenuItemSerializer(
                MenuItem.objects.select_related("category").filter(is_available=True),
                many=True,
            ).data
            featured_items = [
                it for it in available_items if it.get("is_featured")
            ] or available_items[:6]
            coupons = CouponSerializer(
                Coupon.objects.filter(is_active=True), many=True
            ).data
            testimonials = TestimonialSerializer(
                Testimonial.objects.filter(is_featured=True)[:8], many=True
            ).data
            staff = UserSerializer(
                User.objects.filter(is_active=True, is_public_staff=True)[:6],
                many=True,
            ).data
            tables = [
                {
                    "id": t.id,
                    "table_number": t.table_number,
                    "capacity": t.capacity,
                    "zone_name": t.zone.name if t.zone else "Main Hall",
                    "status": t.status,
                }
                for t in DiningTable.objects.select_related("zone").all()
            ]
            settings_data = RestaurantWebsiteSettingsSerializer(settings_obj).data

        return Response(
            {
                "tenant": {
                    **tenant_summary,
                    "theme_id": settings_data["theme_id"],
                    "color_palette": settings_data["color_palette"],
                    "tagline": settings_data["tagline"],
                },
                "settings": settings_data,
                "branches": branches,
                "categories": categories,
                "menu_items": available_items,
                "featured_items": featured_items,
                "active_coupons": coupons,
                "testimonials": testimonials,
                "staff": staff,
                "tables": tables,
            },
            status=status.HTTP_200_OK,
        )


class PublicPlaceOrderView(APIView):
    """Places an online website or QR table order for a restaurant tenant."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, tenant_slug):
        tenant = _resolve_public_tenant(tenant_slug)
        if not tenant or tenant.schema_name == "public":
            return Response(
                {"detail": f"Restaurant '{tenant_slug}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not tenant.is_active or tenant.subscription_status == "SUSPENDED":
            return Response(
                {"code": "TENANT_SUSPENDED", "detail": f"{tenant.name} is suspended."},
                status=status.HTTP_403_FORBIDDEN,
            )

        items_data = request.data.get("items") or []
        if not items_data:
            return Response(
                {"detail": "At least one menu item is required to place an order."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context(tenant.schema_name):
            order_type = (
                request.data.get("order_type") or Order.OrderType.DELIVERY
            ).upper()
            channel = (
                Order.Channel.QR_MENU
                if order_type == Order.OrderType.QR_ORDER
                else Order.Channel.WEBSITE
            )
            customer_name = (
                request.data.get("customer_name")
                or request.data.get("guest_name")
                or "Online Guest"
            ).strip()
            customer_phone = (
                request.data.get("customer_phone")
                or request.data.get("guest_phone")
                or ""
            ).strip()
            customer_address = (
                request.data.get("customer_address") or ""
            ).strip()
            coupon_code = (request.data.get("coupon_code") or "").strip().upper()
            notes = request.data.get("notes") or ""
            table_id = request.data.get("table") or request.data.get("table_id")
            table_number = request.data.get("table_number")

            branch = Branch.objects.filter(is_main_branch=True).first() or Branch.objects.first()
            table_obj = None
            if table_id:
                table_obj = DiningTable.objects.filter(pk=table_id).first()
            elif table_number:
                table_obj = DiningTable.objects.filter(
                    table_number__iexact=str(table_number)
                ).first()

            customer_obj = None
            if customer_phone:
                customer_obj = Customer.objects.filter(
                    phone__icontains=customer_phone
                ).first()
                if not customer_obj:
                    customer_obj = Customer.objects.create(
                        full_name=customer_name,
                        phone=customer_phone,
                        email=request.data.get("customer_email") or "",
                    )

            order = Order.objects.create(
                branch=branch,
                order_type=order_type,
                channel=channel,
                status=Order.Status.IN_KITCHEN,
                payment_status=Order.PaymentStatus.UNPAID,
                payment_method=(
                    request.data.get("payment_method") or Order.PaymentMethod.CASH
                ).upper(),
                table=table_obj,
                customer=customer_obj,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_address=customer_address,
                guest_count=int(request.data.get("guest_count") or 2),
                coupon_code=coupon_code,
                notes=notes,
            )

            for item_data in items_data:
                menu_item_id = item_data.get("menu_item") or item_data.get("id")
                menu_item = (
                    MenuItem.objects.filter(pk=menu_item_id).first()
                    if menu_item_id
                    else None
                )
                item_name = item_data.get("item_name") or item_data.get("name") or (
                    menu_item.name if menu_item else "Menu Dish"
                )
                unit_price = item_data.get("unit_price") or item_data.get("price")
                if unit_price is None:
                    unit_price = menu_item.price if menu_item else Decimal("0.00")
                kitchen_station = (
                    item_data.get("kitchen_station")
                    or (menu_item.kitchen_station if menu_item else "HOT_KITCHEN")
                )
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    item_name=item_name,
                    variant_name=item_data.get("variant_name", ""),
                    kitchen_station=kitchen_station,
                    course=item_data.get("course", OrderItem.Course.MAIN),
                    quantity=int(item_data.get("quantity") or 1),
                    unit_price=Decimal(str(unit_price)),
                    modifiers_json=item_data.get("modifiers_json", []),
                    special_instructions=item_data.get("special_instructions", ""),
                    kot_batch=1,
                    kot_status=OrderItem.KotStatus.QUEUED,
                )

            # Check coupon discount
            if coupon_code:
                coupon = Coupon.objects.filter(
                    code__iexact=coupon_code, is_active=True
                ).first()
                if coupon:
                    sub = sum(
                        Decimal(str(i.unit_price)) * Decimal(str(i.quantity))
                        for i in order.items.all()
                    )
                    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
                        disc = (sub * coupon.discount_value) / Decimal("100.00")
                        if coupon.max_discount_amount:
                            disc = min(disc, coupon.max_discount_amount)
                    else:
                        disc = coupon.discount_value
                    order.discount_amount = round(disc, 2)
                    coupon.used_count += 1
                    coupon.save(update_fields=["used_count"])

            order.recalculate_totals(tenant=tenant)

            if table_obj:
                table_obj.status = DiningTable.Status.OCCUPIED
                table_obj.current_guest_count = order.guest_count
                table_obj.save(update_fields=["status", "current_guest_count"])

            Notification.objects.create(
                branch=branch,
                category=Notification.Category.NEW_ORDER,
                severity=Notification.Severity.INFO,
                title=f"New {order.get_order_type_display()} Order {order.order_number}",
                message=f"{customer_name} placed order {order.order_number} ({order.items.count()} items, {tenant.currency} {order.total_amount}).",
                action_url="/dashboard/kds",
            )

            order_data = OrderSerializer(order).data

        return Response(
            {
                "detail": f"Order {order_data['order_number']} received and sent to the kitchen!",
                "order_number": order_data["order_number"],
                "order": order_data,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicTrackOrderView(APIView):
    """Live order & KOT item status tracking for customers."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, tenant_slug, order_number):
        tenant = _resolve_public_tenant(tenant_slug)
        if not tenant or tenant.schema_name == "public":
            return Response(
                {"detail": f"Restaurant '{tenant_slug}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        with schema_context(tenant.schema_name):
            order = (
                Order.objects.select_related("table", "branch")
                .prefetch_related("items")
                .filter(order_number__iexact=order_number)
                .first()
            )
            if not order:
                return Response(
                    {"detail": f"Order '{order_number}' not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            order_data = OrderSerializer(order).data

        stages = ["PENDING", "IN_KITCHEN", "READY", "SERVED", "COMPLETED"]
        current_idx = (
            stages.index(order_data["status"])
            if order_data["status"] in stages
            else 1
        )
        progress_percent = min(100, int(((current_idx + 1) / len(stages)) * 100))

        return Response(
            {
                "restaurant_name": tenant.name,
                "order_number": order_data["order_number"],
                "status": order_data["status"],
                "payment_status": order_data["payment_status"],
                "order_type": order_data["order_type"],
                "table_number": order_data.get("table_number", ""),
                "progress_percent": progress_percent,
                "estimated_minutes_remaining": (
                    0
                    if order_data["status"] in ("READY", "SERVED", "COMPLETED")
                    else 15
                ),
                "order": order_data,
            },
            status=status.HTTP_200_OK,
        )


class PublicTableReserveView(APIView):
    """Public online table reservation endpoint for a restaurant tenant."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, tenant_slug):
        tenant = _resolve_public_tenant(tenant_slug)
        if not tenant or tenant.schema_name == "public":
            return Response(
                {"detail": f"Restaurant '{tenant_slug}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not tenant.is_active or tenant.subscription_status == "SUSPENDED":
            return Response(
                {"code": "TENANT_SUSPENDED", "detail": f"{tenant.name} is suspended."},
                status=status.HTTP_403_FORBIDDEN,
            )

        with schema_context(tenant.schema_name):
            branch = Branch.objects.filter(is_main_branch=True).first() or Branch.objects.first()
            payload = dict(request.data)
            if branch and not payload.get("branch"):
                payload["branch"] = branch.id

            serializer = TableReservationSerializer(data=payload)
            serializer.is_valid(raise_exception=True)
            reservation = serializer.save()

            Notification.objects.create(
                branch=branch,
                category=Notification.Category.RESERVATION,
                severity=Notification.Severity.INFO,
                title=f"New Reservation: {reservation.guest_name} ({reservation.party_size} guests)",
                message=(
                    f"Table booking {reservation.reservation_code} for {reservation.party_size} guests "
                    f"on {reservation.reservation_date} at {reservation.reservation_time}."
                ),
                action_url="/dashboard/reservations",
            )
            res_data = TableReservationSerializer(reservation).data

        return Response(
            {
                "detail": f"Table reservation {res_data['reservation_code']} confirmed!",
                "reservation_code": res_data["reservation_code"],
                "reservation": res_data,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicSubmitFeedbackView(APIView):
    """Submits guest dining feedback from the public restaurant website."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request, tenant_slug):
        tenant = _resolve_public_tenant(tenant_slug)
        if not tenant or tenant.schema_name == "public":
            return Response(
                {"detail": f"Restaurant '{tenant_slug}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        with schema_context(tenant.schema_name):
            serializer = CustomerFeedbackSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            feedback = serializer.save()
            fb_data = CustomerFeedbackSerializer(feedback).data

        return Response(
            {
                "detail": "Thank you for sharing your dining feedback!",
                "feedback": fb_data,
            },
            status=status.HTTP_201_CREATED,
        )
