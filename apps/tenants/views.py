from decimal import Decimal
from django.db.models import Sum
from django_tenants.utils import schema_context
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsSuperAdmin
from apps.accounts.serializers import UserSerializer
from apps.accounts.views import build_tenant_summary, generate_tokens_for_user
from .models import Client, SubscriptionInvoice, SubscriptionPlan
from .serializers import (
    ClientSerializer,
    SubscriptionInvoiceSerializer,
    SubscriptionPlanSerializer,
)
from .services import provision_restaurant_tenant


class SuperAdminTenantListCreateView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        with schema_context("public"):
            qs = (
                Client.objects.select_related("plan")
                .prefetch_related("domains")
                .exclude(schema_name="public")
                .order_by("id")
            )
            status_filter = request.query_params.get("status")
            if status_filter:
                qs = qs.filter(subscription_status=status_filter)
            return Response(ClientSerializer(qs, many=True).data)

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        slug = (request.data.get("slug") or "").strip().lower()
        if not name or not slug:
            return Response(
                {"detail": "Both name and slug are required to provision a restaurant tenant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context("public"):
            if Client.objects.filter(slug__iexact=slug).exists():
                return Response(
                    {"detail": f"Restaurant workspace '{slug}' already exists."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            plan_id = request.data.get("plan") or request.data.get("plan_id")
            plan_slug = request.data.get("plan_slug") or request.data.get("plan_code")
            plan = None
            if plan_id:
                plan = SubscriptionPlan.objects.filter(pk=plan_id).first()
            if not plan and plan_slug:
                plan = SubscriptionPlan.objects.filter(slug__iexact=plan_slug).first()
            if not plan:
                plan = SubscriptionPlan.objects.first()

        tenant, _ = provision_restaurant_tenant(
            name=name,
            slug=slug,
            owner_name=request.data.get("owner_name") or f"{name} Admin",
            owner_email=request.data.get("owner_email") or f"admin@{slug.replace('-', '')}.com",
            phone=request.data.get("phone") or "+977-1-4429800",
            password=request.data.get("password") or "Admin@12345",
            city=request.data.get("city") or "Kathmandu",
            country=request.data.get("country") or "Nepal",
            cuisine_type=request.data.get("cuisine_type") or "Multi-Cuisine",
            currency=request.data.get("currency") or "NPR",
            pan_vat_number=request.data.get("pan_vat_number") or "609812345",
            plan=plan,
            subscription_status=(
                request.data.get("subscription_status") or "ACTIVE"
            ).upper(),
            theme_id=request.data.get("theme_id") or "bistro-elegance",
            color_palette=request.data.get("color_palette") or "ember-terracotta",
        )

        with schema_context("public"):
            return Response(
                ClientSerializer(tenant).data,
                status=status.HTTP_201_CREATED,
            )


class SuperAdminTenantDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ClientSerializer
    permission_classes = [IsSuperAdmin]

    def get_queryset(self):
        return Client.objects.select_related("plan").prefetch_related("domains")


class SuperAdminSuspendTenantView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        with schema_context("public"):
            tenant = generics.get_object_or_404(Client, pk=pk)
            tenant.subscription_status = Client.SubscriptionStatus.SUSPENDED
            tenant.is_active = False
            tenant.save(update_fields=["subscription_status", "is_active"])
            return Response(ClientSerializer(tenant).data, status=status.HTTP_200_OK)


class SuperAdminActivateTenantView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        with schema_context("public"):
            tenant = generics.get_object_or_404(Client, pk=pk)
            tenant.subscription_status = Client.SubscriptionStatus.ACTIVE
            tenant.is_active = True
            tenant.save(update_fields=["subscription_status", "is_active"])
            return Response(ClientSerializer(tenant).data, status=status.HTTP_200_OK)


class SuperAdminToggleTenantStatusView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        with schema_context("public"):
            tenant = generics.get_object_or_404(Client, pk=pk)
            if (
                not tenant.is_active
                or tenant.subscription_status == Client.SubscriptionStatus.SUSPENDED
            ):
                tenant.subscription_status = Client.SubscriptionStatus.ACTIVE
                tenant.is_active = True
            else:
                tenant.subscription_status = Client.SubscriptionStatus.SUSPENDED
                tenant.is_active = False
            tenant.save(update_fields=["subscription_status", "is_active"])
            return Response(ClientSerializer(tenant).data, status=status.HTTP_200_OK)


class SuperAdminImpersonateTenantView(APIView):
    permission_classes = [IsSuperAdmin]

    def post(self, request, pk):
        with schema_context("public"):
            tenant = generics.get_object_or_404(
                Client.objects.select_related("plan"), pk=pk
            )

        with schema_context(tenant.schema_name):
            target_user = (
                User.objects.filter(
                    is_active=True, role=User.Role.RESTAURANT_ADMIN
                )
                .order_by("id")
                .first()
                or User.objects.filter(is_active=True).order_by("id").first()
            )
            if not target_user:
                return Response(
                    {"detail": "No active staff user found in restaurant workspace."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            tokens = generate_tokens_for_user(target_user, tenant_slug=tenant.slug)
            user_data = UserSerializer(target_user).data

        tenant_summary = build_tenant_summary(tenant)
        return Response(
            {
                **tokens,
                "user": user_data,
                "tenant": tenant_summary,
                "tenant_slug": tenant.slug,
                "redirect_url": "/dashboard",
            },
            status=status.HTTP_200_OK,
        )


class SuperAdminOverviewView(APIView):
    """Cross-schema telemetry across all provisioned restaurant tenants."""

    permission_classes = [IsSuperAdmin]

    def get(self, request):
        with schema_context("public"):
            tenants = (
                Client.objects.select_related("plan")
                .prefetch_related("domains")
                .exclude(schema_name="public")
                .order_by("id")
            )
            tenants_data = ClientSerializer(tenants, many=True).data

            total_tenants = len(tenants_data)
            active_tenants = sum(
                1
                for t in tenants_data
                if t["is_active"] and t["subscription_status"] == "ACTIVE"
            )
            trial_tenants = sum(
                1 for t in tenants_data if t["subscription_status"] == "TRIAL"
            )
            suspended_tenants = sum(
                1
                for t in tenants_data
                if not t["is_active"] or t["subscription_status"] == "SUSPENDED"
            )

            mrr = Decimal("0.00")
            for t_obj in tenants:
                if (
                    t_obj.is_active
                    and t_obj.subscription_status in ("ACTIVE", "TRIAL")
                    and t_obj.plan
                ):
                    mrr += t_obj.plan.price_monthly

            arr = mrr * Decimal("12")
            total_branches = sum(t.get("branches_count", 0) for t in tenants_data)
            total_staff = sum(t.get("staff_count", 0) for t in tenants_data)
            total_tables = sum(t.get("tables_count", 0) for t in tenants_data)
            total_menu_items = sum(t.get("menu_items_count", 0) for t in tenants_data)
            total_orders = sum(t.get("orders_count", 0) for t in tenants_data)
            total_gmv = sum(Decimal(str(t.get("gmv_revenue", 0))) for t in tenants_data)

            invoices_qs = SubscriptionInvoice.objects.select_related(
                "tenant", "plan"
            ).all()
            collected_subscription_revenue = (
                invoices_qs.filter(status="PAID").aggregate(total=Sum("amount"))[
                    "total"
                ]
                or Decimal("0.00")
            )
            recent_invoices = SubscriptionInvoiceSerializer(
                invoices_qs[:15], many=True
            ).data

            plans = SubscriptionPlan.objects.all()
            plan_distribution = [
                {
                    "id": p.id,
                    "name": p.name,
                    "slug": p.slug,
                    "price_monthly": float(p.price_monthly),
                    "tenant_count": p.tenants.exclude(schema_name="public").count(),
                }
                for p in plans
            ]

            return Response(
                {
                    "total_tenants": total_tenants,
                    "active_tenants": active_tenants,
                    "trial_tenants": trial_tenants,
                    "suspended_tenants": suspended_tenants,
                    "total_branches": total_branches,
                    "total_staff": total_staff,
                    "total_tables": total_tables,
                    "total_menu_items": total_menu_items,
                    "total_orders": total_orders,
                    "total_gmv_revenue": float(round(total_gmv, 2)),
                    "subscription_mrr": float(round(mrr, 2)),
                    "subscription_arr": float(round(arr, 2)),
                    "mrr": float(round(mrr, 2)),
                    "arr": float(round(arr, 2)),
                    "collected_subscription_revenue": float(
                        round(collected_subscription_revenue, 2)
                    ),
                    "plan_distribution": plan_distribution,
                    "tenants": tenants_data,
                    "subscription_invoices": recent_invoices,
                    "recent_invoices": recent_invoices,
                },
                status=status.HTTP_200_OK,
            )


class SuperAdminPlanListCreateView(generics.ListCreateAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsSuperAdmin]


class SuperAdminPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsSuperAdmin]


class SuperAdminInvoiceListCreateView(generics.ListCreateAPIView):
    queryset = SubscriptionInvoice.objects.select_related("tenant", "plan").all()
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [IsSuperAdmin]


class SuperAdminInvoiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SubscriptionInvoice.objects.select_related("tenant", "plan").all()
    serializer_class = SubscriptionInvoiceSerializer
    permission_classes = [IsSuperAdmin]


class PublicPlansListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    serializer_class = SubscriptionPlanSerializer

    def get_queryset(self):
        return SubscriptionPlan.objects.filter(is_active=True).order_by("price_monthly")


class PublicRestaurantsListView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        with schema_context("public"):
            tenants = (
                Client.objects.select_related("plan")
                .prefetch_related("domains")
                .exclude(schema_name="public")
                .filter(is_active=True)
                .order_by("id")
            )
            return Response(
                ClientSerializer(tenants, many=True).data,
                status=status.HTTP_200_OK,
            )


class PublicLandingView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        with schema_context("public"):
            plans = SubscriptionPlan.objects.filter(is_active=True).order_by(
                "price_monthly"
            )
            tenants = (
                Client.objects.select_related("plan")
                .prefetch_related("domains")
                .exclude(schema_name="public")
                .order_by("id")
            )
            plans_data = SubscriptionPlanSerializer(plans, many=True).data
            tenants_data = ClientSerializer(tenants, many=True).data
            return Response(
                {
                    "plans": plans_data,
                    "restaurants": tenants_data,
                    "tenants": tenants_data,
                },
                status=status.HTTP_200_OK,
            )


class PublicOnboardRestaurantView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        slug = (request.data.get("slug") or "").strip().lower()
        owner_name = (request.data.get("owner_name") or "").strip() or f"{name} Owner"
        owner_email = (request.data.get("owner_email") or "").strip().lower()
        phone = (
            request.data.get("phone")
            or request.data.get("owner_phone")
            or "+977-1-4429800"
        ).strip()
        password = request.data.get("password") or "Admin@12345"
        city = (request.data.get("city") or "Kathmandu").strip()
        country = (request.data.get("country") or "Nepal").strip()
        cuisine_type = (
            request.data.get("cuisine_type") or "Multi-Cuisine & Grill"
        ).strip()
        currency = (request.data.get("currency") or "NPR").strip()
        pan_vat_number = (request.data.get("pan_vat_number") or "609812345").strip()
        theme_id = request.data.get("theme_id") or "bistro-elegance"
        color_palette = request.data.get("color_palette") or "ember-terracotta"

        if not name or not slug:
            return Response(
                {"detail": "Restaurant name and slug are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with schema_context("public"):
            if Client.objects.filter(slug__iexact=slug).exists():
                return Response(
                    {"detail": f"Workspace slug '{slug}' is already taken."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            plan_id = request.data.get("plan") or request.data.get("plan_id")
            plan_slug = (
                request.data.get("plan_slug")
                or request.data.get("plan_code")
                or "growth"
            )
            plan = None
            if plan_id:
                plan = SubscriptionPlan.objects.filter(pk=plan_id).first()
            if not plan and plan_slug:
                plan = SubscriptionPlan.objects.filter(slug__iexact=plan_slug).first()
            if not plan:
                plan = SubscriptionPlan.objects.first()

        tenant, admin_user = provision_restaurant_tenant(
            name=name,
            slug=slug,
            owner_name=owner_name,
            owner_email=owner_email or f"admin@{slug.replace('-', '')}.com",
            phone=phone,
            password=password,
            city=city,
            country=country,
            cuisine_type=cuisine_type,
            currency=currency,
            pan_vat_number=pan_vat_number,
            plan=plan,
            subscription_status="ACTIVE",
            theme_id=theme_id,
            color_palette=color_palette,
            seed_starter_data=True,
        )

        with schema_context(tenant.schema_name):
            tokens = generate_tokens_for_user(admin_user, tenant_slug=tenant.slug)
            user_data = UserSerializer(admin_user).data

        tenant_summary = build_tenant_summary(tenant)
        return Response(
            {
                **tokens,
                "user": user_data,
                "tenant": tenant_summary,
                "detail": f"Restaurant workspace '{name}' provisioned with starter menu, floor tables, and POS register.",
            },
            status=status.HTTP_201_CREATED,
        )
