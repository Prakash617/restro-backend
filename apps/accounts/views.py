from django.utils import timezone
from django_tenants.utils import schema_context
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.tenants.models import Client
from .models import AuditLog, StaffShift, User
from .permissions import IsRestaurantStaff
from .serializers import AuditLogSerializer, StaffShiftSerializer, UserSerializer


def build_tenant_summary(tenant):
    if not tenant or getattr(tenant, "schema_name", "public") == "public":
        return {
            "id": tenant.id if tenant else 1,
            "slug": "public",
            "name": "RestoCloud SaaS Platform",
            "schema_name": "public",
            "cuisine_type": "Platform",
            "subscription_status": "ACTIVE",
            "plan_name": "Platform SuperAdmin",
            "plan_code": "PLATFORM",
            "city": "Kathmandu",
            "country": "Nepal",
            "currency": "NPR",
            "pan_vat_number": "",
            "tax_system": "VAT_13_NP",
            "tax_rate_percent": "13.00",
            "service_charge_percent": "10.00",
            "max_branches": 99,
            "max_staff_users": 999,
            "max_tables": 999,
            "max_menu_items": 9999,
            "enable_pos": True,
            "enable_kds": True,
            "enable_inventory": True,
            "enable_online_ordering": True,
            "enable_table_reservations": True,
            "enable_loyalty_crm": True,
            "enable_multi_branch": True,
            "enable_advanced_analytics": True,
            "kds_enabled": True,
            "online_ordering_enabled": True,
            "table_reservations_enabled": True,
        }
    plan = getattr(tenant, "plan", None)
    return {
        "id": tenant.id,
        "slug": tenant.slug,
        "name": tenant.name,
        "schema_name": tenant.schema_name,
        "cuisine_type": tenant.cuisine_type,
        "subscription_status": tenant.subscription_status,
        "plan_name": plan.name if plan else "Enterprise",
        "plan_code": plan.slug.upper() if plan else "ENTERPRISE",
        "city": tenant.city,
        "country": tenant.country,
        "currency": tenant.currency,
        "pan_vat_number": tenant.pan_vat_number,
        "tax_system": tenant.tax_system,
        "tax_rate_percent": str(tenant.tax_rate_percent),
        "is_tax_inclusive": tenant.is_tax_inclusive,
        "service_charge_percent": str(tenant.service_charge_percent),
        "fiscal_year": tenant.fiscal_year,
        "max_branches": plan.max_branches if plan else 5,
        "max_staff_users": plan.max_staff_users if plan else 25,
        "max_tables": plan.max_tables if plan else 40,
        "max_menu_items": plan.max_menu_items if plan else 250,
        "enable_pos": plan.enable_pos if plan else True,
        "enable_kds": plan.enable_kds if plan else True,
        "enable_inventory": plan.enable_inventory if plan else True,
        "enable_online_ordering": plan.enable_online_ordering if plan else True,
        "enable_table_reservations": plan.enable_table_reservations if plan else True,
        "enable_loyalty_crm": plan.enable_loyalty_crm if plan else True,
        "enable_multi_branch": plan.enable_multi_branch if plan else True,
        "enable_advanced_analytics": plan.enable_advanced_analytics if plan else True,
        "kds_enabled": plan.enable_kds if plan else True,
        "online_ordering_enabled": plan.enable_online_ordering if plan else True,
        "table_reservations_enabled": plan.enable_table_reservations if plan else True,
    }


def generate_tokens_for_user(user, tenant_slug="public"):
    refresh = RefreshToken.for_user(user)
    refresh["tenant_slug"] = tenant_slug
    refresh["role"] = user.role
    refresh["email"] = user.email
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        explicit_slug = (
            request.data.get("tenant_slug")
            or request.META.get("HTTP_X_TENANT_SLUG")
            or ""
        ).strip().lower()

        if not email or not password:
            return Response(
                {"detail": "Both email and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_tenant = None
        with schema_context("public"):
            if explicit_slug and explicit_slug != "public":
                target_tenant = (
                    Client.objects.select_related("plan")
                    .filter(slug__iexact=explicit_slug)
                    .first()
                )
                if not target_tenant:
                    return Response(
                        {"detail": f"Restaurant workspace '{explicit_slug}' not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )
                if not target_tenant.is_active or target_tenant.subscription_status == "SUSPENDED":
                    return Response(
                        {
                            "code": "TENANT_SUSPENDED",
                            "detail": f"{target_tenant.name} workspace is currently suspended by platform administration.",
                            "tenant": target_tenant.name,
                            "tenant_name": target_tenant.name,
                            "tenant_slug": target_tenant.slug,
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
            else:
                target_tenant = Client.objects.filter(schema_name="public").first()

        authenticated_user = None
        resolved_tenant = target_tenant
        target_schema = target_tenant.schema_name if target_tenant else "public"

        with schema_context(target_schema):
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user and user.check_password(password):
                authenticated_user = user

        # Fallback: if user wasn't found in the specified schema (e.g. SuperAdmin logging in while a tenant slug is cached, or staff logging in without explicit slug)
        if not authenticated_user:
            with schema_context("public"):
                pub_user = User.objects.filter(email__iexact=email, is_active=True).first()
                if pub_user and pub_user.check_password(password):
                    authenticated_user = pub_user
                    resolved_tenant = Client.objects.filter(schema_name="public").first()

        if not authenticated_user and not explicit_slug:
            with schema_context("public"):
                tenants = list(
                    Client.objects.select_related("plan").exclude(schema_name="public")
                )
            for t in tenants:
                with schema_context(t.schema_name):
                    u = User.objects.filter(email__iexact=email, is_active=True).first()
                    if u and u.check_password(password):
                        if not t.is_active or t.subscription_status == "SUSPENDED":
                            return Response(
                                {
                                    "code": "TENANT_SUSPENDED",
                                    "detail": f"{t.name} workspace is currently suspended by platform administration.",
                                    "tenant": t.name,
                                    "tenant_name": t.name,
                                    "tenant_slug": t.slug,
                                },
                                status=status.HTTP_403_FORBIDDEN,
                            )
                        authenticated_user = u
                        resolved_tenant = t
                        break

        if not authenticated_user:
            return Response(
                {"detail": "Invalid email or password for this restaurant workspace."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tenant_summary = build_tenant_summary(resolved_tenant)
        with schema_context(resolved_tenant.schema_name if resolved_tenant else "public"):
            user_data = UserSerializer(authenticated_user).data
            tokens = generate_tokens_for_user(
                authenticated_user,
                tenant_slug=tenant_summary["slug"],
            )

        return Response(
            {
                **tokens,
                "user": user_data,
                "tenant": tenant_summary,
            },
            status=status.HTTP_200_OK,
        )


class PinLoginView(APIView):
    """Fast POS operator switch using a 4-digit PIN on the active tenant schema."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        pin = str(request.data.get("pin") or "").strip()
        explicit_slug = (
            request.data.get("tenant_slug")
            or request.META.get("HTTP_X_TENANT_SLUG")
            or ""
        ).strip().lower()

        if not pin:
            return Response(
                {"detail": "POS PIN is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = getattr(request, "tenant", None)
        if (not tenant or tenant.schema_name == "public") and explicit_slug and explicit_slug != "public":
            with schema_context("public"):
                tenant = (
                    Client.objects.select_related("plan")
                    .filter(slug__iexact=explicit_slug)
                    .first()
                )

        if not tenant or tenant.schema_name == "public":
            return Response(
                {
                    "code": "TENANT_REQUIRED",
                    "detail": "Please select an active restaurant workspace for POS PIN login.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not tenant.is_active or tenant.subscription_status == "SUSPENDED":
            return Response(
                {
                    "code": "TENANT_SUSPENDED",
                    "detail": f"{tenant.name} workspace is currently suspended.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        with schema_context(tenant.schema_name):
            user = (
                User.objects.select_related("branch")
                .filter(pos_pin=pin, is_active=True)
                .first()
            )
            if not user:
                return Response(
                    {"detail": "Invalid POS PIN. No active staff member matched."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            user_data = UserSerializer(user).data
            tokens = generate_tokens_for_user(user, tenant_slug=tenant.slug)

        tenant_summary = build_tenant_summary(tenant)
        return Response(
            {
                **tokens,
                "user": user_data,
                "tenant": tenant_summary,
            },
            status=status.HTTP_200_OK,
        )


class TokenRefreshView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_refresh = request.data.get("refresh") or ""
        if not raw_refresh:
            return Response(
                {"detail": "refresh token is required.", "code": "refresh_required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError:
            return Response(
                {
                    "detail": "Refresh token is invalid or has expired. Please sign in again.",
                    "code": "token_not_valid",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token_slug = str(refresh.payload.get("tenant_slug") or "").strip().lower()
        header_slug = (request.META.get("HTTP_X_TENANT_SLUG") or "").strip().lower()
        if (
            token_slug
            and header_slug
            and header_slug != "public"
            and token_slug != header_slug
        ):
            return Response(
                {
                    "detail": "Refresh token does not belong to the active restaurant workspace.",
                    "code": "tenant_token_mismatch",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = TokenRefreshSerializer(data={"refresh": raw_refresh})
        if not serializer.is_valid():
            return Response(
                {
                    "detail": "Refresh token is invalid or has expired. Please sign in again.",
                    "code": "token_not_valid",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        user_data = UserSerializer(request.user).data
        tenant_summary = build_tenant_summary(tenant)
        return Response(
            {
                **user_data,
                "user": user_data,
                "tenant": tenant_summary,
            }
        )

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        tenant = getattr(request, "tenant", None)
        user_data = serializer.data
        tenant_summary = build_tenant_summary(tenant)
        return Response(
            {
                **user_data,
                "user": user_data,
                "tenant": tenant_summary,
            }
        )


class StaffListCreateView(generics.ListCreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = User.objects.select_related("branch").all().order_by("id")
        role = self.request.query_params.get("role")
        branch = self.request.query_params.get("branch")
        if role:
            qs = qs.filter(role=role)
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs

    def create(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(tenant, "schema_name", "public") != "public" and getattr(tenant, "plan", None):
            max_staff = tenant.plan.max_staff_users
            current_staff = User.objects.count()
            if current_staff >= max_staff:
                return Response(
                    {
                        "code": "QUOTA_EXCEEDED",
                        "detail": (
                            f"Staff quota reached ({current_staff}/{max_staff}) for the "
                            f"{tenant.plan.name} plan. Please upgrade your subscription plan."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)


class StaffDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.select_related("branch").all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]


class StaffShiftListCreateView(generics.ListCreateAPIView):
    serializer_class = StaffShiftSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = StaffShift.objects.select_related("staff", "branch").all()
        branch = self.request.query_params.get("branch")
        shift_date = self.request.query_params.get("shift_date")
        status_param = self.request.query_params.get("status")
        if branch:
            qs = qs.filter(branch_id=branch)
        if shift_date:
            qs = qs.filter(shift_date=shift_date)
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class StaffShiftDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = StaffShift.objects.select_related("staff", "branch").all()
    serializer_class = StaffShiftSerializer
    permission_classes = [permissions.AllowAny]


class StaffShiftClockInView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        shift = generics.get_object_or_404(StaffShift, pk=pk)
        shift.status = StaffShift.Status.CHECKED_IN
        shift.clock_in_at = timezone.now()
        shift.save(update_fields=["status", "clock_in_at"])
        return Response(StaffShiftSerializer(shift).data, status=status.HTTP_200_OK)


class StaffShiftClockOutView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        shift = generics.get_object_or_404(StaffShift, pk=pk)
        shift.status = StaffShift.Status.COMPLETED
        shift.clock_out_at = timezone.now()
        shift.save(update_fields=["status", "clock_out_at"])
        return Response(StaffShiftSerializer(shift).data, status=status.HTTP_200_OK)


class AuditLogListView(generics.ListAPIView):
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor", "branch").all()
        action = self.request.query_params.get("action")
        branch = self.request.query_params.get("branch")
        if action:
            qs = qs.filter(action=action)
        if branch:
            qs = qs.filter(branch_id=branch)
        return qs[:200]
