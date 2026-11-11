from datetime import timedelta
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
from django_tenants.utils import schema_context

from .models import Client, Domain, SubscriptionInvoice, SubscriptionPlan


def get_tenant_live_metrics(tenant):
    if not tenant or tenant.schema_name == "public":
        return {
            "branches_count": 0,
            "staff_count": 0,
            "tables_count": 0,
            "menu_items_count": 0,
            "orders_count": 0,
            "gmv_revenue": 0.0,
            "theme_id": "bistro-elegance",
            "color_palette": "ember-terracotta",
        }
    try:
        from apps.accounts.models import User
        from apps.branches.models import Branch
        from apps.menu.models import MenuItem
        from apps.orders.models import Order
        from apps.tables.models import DiningTable
        from apps.website.models import RestaurantWebsiteSettings

        with schema_context(tenant.schema_name):
            branches_count = Branch.objects.count()
            staff_count = User.objects.count()
            tables_count = DiningTable.objects.count()
            menu_items_count = MenuItem.objects.count()
            orders_qs = Order.objects.exclude(status=Order.Status.CANCELLED)
            orders_count = orders_qs.count()
            gmv = (
                orders_qs.aggregate(total=Sum("total_amount"))["total"]
                or Decimal("0.00")
            )
            ws = RestaurantWebsiteSettings.objects.first()
            theme_id = ws.theme_id if ws else "bistro-elegance"
            color_palette = ws.color_palette if ws else "ember-terracotta"
            return {
                "branches_count": branches_count,
                "staff_count": staff_count,
                "tables_count": tables_count,
                "menu_items_count": menu_items_count,
                "orders_count": orders_count,
                "gmv_revenue": float(round(gmv, 2)),
                "theme_id": theme_id,
                "color_palette": color_palette,
            }
    except Exception:
        return {
            "branches_count": 1,
            "staff_count": 1,
            "tables_count": 0,
            "menu_items_count": 0,
            "orders_count": 0,
            "gmv_revenue": 0.0,
            "theme_id": "bistro-elegance",
            "color_palette": "ember-terracotta",
        }


def provision_restaurant_tenant(
    *,
    name,
    slug,
    owner_name="",
    owner_email="",
    phone="+977-1-4429800",
    password="Admin@12345",
    city="Kathmandu",
    country="Nepal",
    cuisine_type="Multi-Cuisine & Wood-Fired Grill",
    currency="NPR",
    pan_vat_number="609812345",
    plan=None,
    subscription_status="ACTIVE",
    theme_id="bistro-elegance",
    color_palette="ember-terracotta",
    seed_starter_data=True,
):
    from apps.accounts.models import User
    from apps.branches.models import Branch
    from apps.finance.models import CashRegisterSession
    from apps.menu.models import MenuCategory, MenuItem
    from apps.tables.models import DiningTable, DiningZone
    from apps.website.models import RestaurantWebsiteSettings

    clean_slug = slug.strip().lower()
    schema_name = clean_slug.replace("-", "_")
    owner_name = owner_name or f"{name} Owner"
    owner_email = owner_email or f"admin@{clean_slug.replace('-', '')}.com"

    with schema_context("public"):
        if not plan:
            plan = (
                SubscriptionPlan.objects.filter(slug="growth").first()
                or SubscriptionPlan.objects.first()
            )
        tenant = Client.objects.create(
            schema_name=schema_name,
            name=name,
            slug=clean_slug,
            plan=plan,
            subscription_status=subscription_status,
            trial_ends_at=timezone.now() + timedelta(days=14),
            is_active=(subscription_status != "SUSPENDED"),
            owner_name=owner_name,
            owner_email=owner_email,
            phone=phone,
            city=city,
            country=country,
            cuisine_type=cuisine_type,
            currency=currency,
            pan_vat_number=pan_vat_number,
        )
        Domain.objects.get_or_create(
            domain=f"{clean_slug}.localhost",
            defaults={"tenant": tenant, "is_primary": True},
        )
        if plan:
            SubscriptionInvoice.objects.get_or_create(
                invoice_number=f"SUB-{clean_slug[:6].upper()}-001",
                defaults={
                    "tenant": tenant,
                    "plan": plan,
                    "billing_cycle": SubscriptionInvoice.BillingCycle.MONTHLY,
                    "amount": plan.price_monthly,
                    "currency": "USD",
                    "payment_gateway": SubscriptionInvoice.PaymentGateway.STRIPE,
                    "status": SubscriptionInvoice.Status.PAID,
                    "period_start": timezone.now().date(),
                    "period_end": (timezone.now() + timedelta(days=30)).date(),
                },
            )

    with schema_context(tenant.schema_name):
        main_branch = Branch.objects.create(
            name=f"{name} — Main Flagship",
            code="MAIN-01",
            slug="main-flagship",
            is_main_branch=True,
            address=f"Central {city}",
            city=city,
            phone=phone,
            email=owner_email,
            manager_name=owner_name,
            pan_vat_number=pan_vat_number,
            tax_rate_percent=tenant.tax_rate_percent,
            service_charge_percent=tenant.service_charge_percent,
        )

        admin_user = User.objects.create_user(
            email=owner_email,
            password=password,
            full_name=owner_name,
            role=User.Role.RESTAURANT_ADMIN,
            phone=phone,
            department="Management",
            specialization="Executive Operations",
            branch=main_branch,
            pos_pin="1111",
            is_staff=True,
            is_superuser=True,
        )

        RestaurantWebsiteSettings.objects.create(
            theme_id=theme_id,
            color_palette=color_palette,
            tagline=f"Signature {cuisine_type} in {city}",
            hero_title=f"Welcome to {name}",
            hero_subtitle=f"Experience handcrafted {cuisine_type.lower()}, warm hospitality, and effortless online ordering or table booking.",
            address=f"Central {city}, {country}",
            phone=phone,
            email=owner_email,
        )

        if seed_starter_data:
            cat_starters = MenuCategory.objects.create(
                name="Signature Starters",
                slug="signature-starters",
                description="Handcrafted appetizers and small plates",
                display_order=1,
            )
            cat_mains = MenuCategory.objects.create(
                name="Chef's Mains & Grill",
                slug="chefs-mains-grill",
                description="House specialties prepared fresh to order",
                display_order=2,
            )
            cat_drinks = MenuCategory.objects.create(
                name="Artisan Beverages",
                slug="artisan-beverages",
                description="Craft mocktails, coffee, and refreshments",
                display_order=3,
            )

            MenuItem.objects.create(
                category=cat_starters,
                name="Chargrilled Herb Flatbread & Dip",
                price=Decimal("420.00"),
                cost_price=Decimal("130.00"),
                prep_time_minutes=10,
                kitchen_station=MenuItem.KitchenStation.GRILL,
                is_vegetarian=True,
                is_featured=True,
                variants_json=[
                    {"name": "Regular", "price": 0},
                    {"name": "Sharing Platter", "price": 180},
                ],
                modifiers_json=[{"name": "Extra Truffle Oil", "price": 90}],
            )
            MenuItem.objects.create(
                category=cat_mains,
                name=f"{name} Signature Platter",
                price=Decimal("880.00"),
                cost_price=Decimal("290.00"),
                prep_time_minutes=18,
                kitchen_station=MenuItem.KitchenStation.HOT_KITCHEN,
                is_featured=True,
                variants_json=[
                    {"name": "Regular", "price": 0},
                    {"name": "Large", "price": 220},
                ],
                modifiers_json=[{"name": "Extra Side Sauce", "price": 60}],
            )
            MenuItem.objects.create(
                category=cat_drinks,
                name="Himalayan Spiced Iced Tea",
                price=Decimal("260.00"),
                cost_price=Decimal("65.00"),
                prep_time_minutes=5,
                kitchen_station=MenuItem.KitchenStation.BAR,
                is_vegetarian=True,
                is_vegan=True,
            )

            zone = DiningZone.objects.create(
                branch=main_branch,
                name="Main Dining Hall",
                code="HALL-A",
                floor_number=1,
            )
            for idx in range(1, 7):
                DiningTable.objects.create(
                    branch=main_branch,
                    zone=zone,
                    table_number=f"T-{idx:02d}",
                    capacity=4 if idx <= 4 else 6,
                    shape=(
                        DiningTable.Shape.SQUARE
                        if idx <= 4
                        else DiningTable.Shape.RECTANGLE
                    ),
                    pos_x=((idx - 1) % 3) * 180 + 40,
                    pos_y=((idx - 1) // 3) * 160 + 40,
                )

            CashRegisterSession.objects.create(
                branch=main_branch,
                opened_by=admin_user,
                register_name="Main POS Register #1",
                opening_float=Decimal("5000.00"),
            )

    return tenant, admin_user
