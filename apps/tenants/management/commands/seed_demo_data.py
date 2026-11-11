from datetime import date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.accounts.models import AuditLog, StaffShift, User
from apps.branches.models import Branch
from apps.customers.models import (
    Coupon,
    Customer,
    CustomerFeedback,
    LoyaltyTransaction,
)
from apps.finance.models import CashRegisterSession, Expense, TaxInvoice
from apps.inventory.models import (
    InventoryItem,
    PurchaseOrder,
    PurchaseOrderItem,
    RecipeIngredient,
    StockMovement,
    Supplier,
)
from apps.menu.models import MenuCategory, MenuItem
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem, PaymentTransaction
from apps.reservations.models import TableReservation
from apps.tables.models import DiningTable, DiningZone
from apps.tenants.models import (
    Client,
    Domain,
    SubscriptionInvoice,
    SubscriptionPlan,
)
from apps.website.models import RestaurantWebsiteSettings, Testimonial


DEMO_TENANTS = [
    {
        "slug": "himalayan-hearth",
        "name": "Himalayan Hearth & Grill",
        "cuisine_type": "Nepali & Wood-Fired Grill",
        "owner_name": "Aarav Thapa",
        "owner_email": "admin@himalayanhearth.com",
        "phone": "+977-1-4429800",
        "city": "Kathmandu",
        "country": "Nepal",
        "currency": "NPR",
        "pan_vat_number": "609812345",
        "plan_slug": "enterprise",
        "theme_id": "bistro-elegance",
        "color_palette": "ember-terracotta",
        "tagline": "Artisan Wood-Fired Momos, Thakali Platter & Smoked Mountain Grill",
        "hero_title": "Wood-Fired Himalayan Gastronomy in the Heart of Kathmandu",
        "hero_subtitle": "Hand-pleated jhol momos, Mustang jimbu thakali platters, and chargrilled mountain meats crafted over oak and rhododendron embers.",
        "chef_name": "Chef Aarav Thapa",
        "chef_title": "Executive Hearth Master",
        "branches": [
            {
                "name": "Thamel Flagship Hearth",
                "code": "KTM-THM-01",
                "slug": "thamel-flagship",
                "is_main_branch": True,
                "address": "Mandala Street, Thamel, Kathmandu",
                "city": "Kathmandu",
                "phone": "+977-1-4429800",
            },
            {
                "name": "Jhamsikhel Garden Lounge",
                "code": "LTP-JHM-02",
                "slug": "jhamsikhel-lounge",
                "is_main_branch": False,
                "address": "Jhamsikhel Road, Lalitpur",
                "city": "Lalitpur",
                "phone": "+977-1-5543210",
            },
        ],
        "dishes": [
            ("Starters & Momos", "Smoked Buff Jhol Momo", "480.00", "150.00", "HOT_KITCHEN", False, "MEDIUM", True),
            ("Starters & Momos", "Chargrilled Wild Boar Choila", "650.00", "220.00", "GRILL", False, "HOT", True),
            ("Starters & Momos", "Crispy Himalayan Timur Fries", "340.00", "95.00", "HOT_KITCHEN", True, "MILD", False),
            ("Starters & Momos", "Mustang Buckwheat Phapar Crepe", "390.00", "110.00", "HOT_KITCHEN", True, "NONE", False),
            ("Wood-Fired Mains", "Royal Mustang Thakali Mutton Thali", "980.00", "340.00", "HOT_KITCHEN", False, "MEDIUM", True),
            ("Wood-Fired Mains", "Wood-Fired Rainbow Trout & Herbs", "1150.00", "410.00", "GRILL", False, "MILD", True),
            ("Wood-Fired Mains", "Smoked Pork Ribs in Gundruk Glaze", "1050.00", "360.00", "GRILL", False, "MEDIUM", False),
            ("Wood-Fired Mains", "Organic Paneer & Wild Mushroom Sekuwa", "720.00", "230.00", "GRILL", True, "MEDIUM", False),
            ("Artisan Desserts", "Warm Khuwa & Juju Dhau Tart", "420.00", "125.00", "BAKERY", True, "NONE", True),
            ("Artisan Desserts", "Dark Chocolate & Timur Mousse", "460.00", "140.00", "COLD_PANTRY", True, "NONE", False),
            ("Craft Beverages", "Ilam First-Flush Spiced Kombucha", "280.00", "70.00", "BAR", True, "NONE", False),
            ("Craft Beverages", "Rhododendron & Himalayan Honey Spritz", "350.00", "85.00", "BAR", True, "NONE", True),
        ],
    },
    {
        "slug": "tokyo-ramen",
        "name": "Tokyo Ramen & Izakaya Lab",
        "cuisine_type": "Japanese Ramen & Craft Izakaya",
        "owner_name": "Kenji Takahashi",
        "owner_email": "admin@tokyoramen.com",
        "phone": "+977-1-4438811",
        "city": "Kathmandu",
        "country": "Nepal",
        "currency": "NPR",
        "pan_vat_number": "609854321",
        "plan_slug": "growth",
        "theme_id": "urban-street",
        "color_palette": "berry-bistro",
        "tagline": "18-Hour Tonkotsu Broth, Hand-Pulled Noodles & Late-Night Yakitori",
        "hero_title": "18-Hour Simmered Tonkotsu & Binchotan Charcoal Yakitori",
        "hero_subtitle": "High-energy Shinjuku alley vibes with rich collagen broths, house-made alkaline noodles, and smoky robata skewers.",
        "chef_name": "Chef Kenji Takahashi",
        "chef_title": "Master Ramen & Robata Chef",
        "branches": [
            {
                "name": "Lazimpat Izakaya Flagship",
                "code": "TYO-LAZ-01",
                "slug": "lazimpat-flagship",
                "is_main_branch": True,
                "address": "Embassy Lane, Lazimpat, Kathmandu",
                "city": "Kathmandu",
                "phone": "+977-1-4438811",
            },
            {
                "name": "Boudha Express Ramen Bar",
                "code": "TYO-BDH-02",
                "slug": "boudha-express",
                "is_main_branch": False,
                "address": "Boudha Stupa Circle, Kathmandu",
                "city": "Kathmandu",
                "phone": "+977-1-4912345",
            },
        ],
        "dishes": [
            ("Izakaya Small Plates", "Crispy Pork & Ginger Gyoza (6 pcs)", "460.00", "140.00", "HOT_KITCHEN", False, "MILD", True),
            ("Izakaya Small Plates", "Binchotan Chicken Tsukune Skewers", "520.00", "165.00", "GRILL", False, "NONE", True),
            ("Izakaya Small Plates", "Truffle Edamame with Maldon Sea Salt", "340.00", "90.00", "COLD_PANTRY", True, "NONE", False),
            ("Izakaya Small Plates", "Takoyaki Octopus Street Balls", "540.00", "180.00", "HOT_KITCHEN", False, "MILD", False),
            ("Signature Ramen Bowls", "Black Garlic Truffle Tonkotsu Ramen", "920.00", "310.00", "HOT_KITCHEN", False, "MILD", True),
            ("Signature Ramen Bowls", "Volcano Spicy Tantanmen Ramen", "890.00", "290.00", "HOT_KITCHEN", False, "EXTRA_HOT", True),
            ("Signature Ramen Bowls", "Shoyu Duck Breast & Bamboo Ramen", "960.00", "330.00", "HOT_KITCHEN", False, "NONE", False),
            ("Signature Ramen Bowls", "Creamy Shiitake & Miso Vegan Ramen", "820.00", "240.00", "HOT_KITCHEN", True, "MILD", False),
            ("Artisan Desserts", "Uji Matcha Basque Cheesecake", "480.00", "150.00", "BAKERY", True, "NONE", True),
            ("Craft Beverages", "Yuzu & Ginger Highball Cooler", "360.00", "95.00", "BAR", True, "NONE", True),
        ],
    },
    {
        "slug": "lumiere-dining",
        "name": "Lumière Fine Dining",
        "cuisine_type": "Modern French Gastronomy",
        "owner_name": "Claire Laurent",
        "owner_email": "admin@lumieredining.com",
        "phone": "+977-1-4229900",
        "city": "Kathmandu",
        "country": "Nepal",
        "currency": "NPR",
        "pan_vat_number": "609877788",
        "plan_slug": "enterprise",
        "theme_id": "fine-dining-gold",
        "color_palette": "midnight-gold",
        "tagline": "Seasonal Tasting Menus, Dry-Aged Cuts & Sommelier Cellar Pairings",
        "hero_title": "Contemporary French Haute Cuisine & Tasting Experiences",
        "hero_subtitle": "An intimate candlelit sanctuary celebrating classical French technique, seasonal micro-harvests, and cellar-aged pairings.",
        "chef_name": "Chef Claire Laurent",
        "chef_title": "Chef de Cuisine",
        "branches": [
            {
                "name": "Babar Mahal Heritage Salon",
                "code": "LUM-BBR-01",
                "slug": "babar-mahal-salon",
                "is_main_branch": True,
                "address": "Babar Mahal Revisited, Kathmandu",
                "city": "Kathmandu",
                "phone": "+977-1-4229900",
            },
            {
                "name": "Patan Rooftop Conservatory",
                "code": "LUM-PTN-02",
                "slug": "patan-conservatory",
                "is_main_branch": False,
                "address": "Patan Durbar Square, Lalitpur",
                "city": "Lalitpur",
                "phone": "+977-1-5529900",
            },
        ],
        "dishes": [
            ("Les Entrées", "Seared Scallops & Cauliflower Velouté", "1250.00", "450.00", "HOT_KITCHEN", False, "NONE", True),
            ("Les Entrées", "Wild Mushroom & Black Truffle Tartlet", "980.00", "320.00", "BAKERY", True, "NONE", True),
            ("Les Entrées", "Heirloom Beetroot Carpaccio & Goat Cheese", "860.00", "260.00", "COLD_PANTRY", True, "NONE", False),
            ("Les Plats Principaux", "Pan-Seared Duck Breast & Black Truffle Jus", "1850.00", "640.00", "GRILL", False, "NONE", True),
            ("Les Plats Principaux", "45-Day Dry-Aged Tenderloin Rossini", "2450.00", "890.00", "GRILL", False, "NONE", True),
            ("Les Plats Principaux", "Butter-Poached Sea Bass & Saffron Beurre Blanc", "1920.00", "680.00", "HOT_KITCHEN", False, "NONE", False),
            ("Les Plats Principaux", "Saffron Risotto & Morel Mushrooms", "1420.00", "430.00", "HOT_KITCHEN", True, "NONE", False),
            ("Les Desserts", "Valrhona 70% Chocolate Soufflé", "780.00", "210.00", "BAKERY", True, "NONE", True),
            ("Les Desserts", "Madagascar Vanilla Bean Crème Brûlée", "690.00", "180.00", "BAKERY", True, "NONE", False),
            ("Cellar & Zero-Proof", "Botanical Elderflower & Rosehip Sparkler", "520.00", "130.00", "BAR", True, "NONE", True),
        ],
    },
    {
        "slug": "nordic-roast",
        "name": "Nordic Roast & Artisan Bakery",
        "cuisine_type": "Specialty Coffee & Sourdough Bakery",
        "owner_name": "Soren Lindqvist",
        "owner_email": "admin@nordicroast.com",
        "phone": "+977-1-4411223",
        "city": "Kathmandu",
        "country": "Nepal",
        "currency": "NPR",
        "pan_vat_number": "609899900",
        "plan_slug": "starter",
        "theme_id": "cafe-minimal",
        "color_palette": "espresso-warm",
        "tagline": "Single-Origin Micro-Lot Roastery, Cardamom Buns & All-Day Brunch",
        "hero_title": "Scandinavian Daylight Roastery & Sourdough Boulangerie",
        "hero_subtitle": "36-hour fermented country sourdough, braided Swedish cardamom knots, and single-origin Himalayan & Ethiopian filter pours.",
        "chef_name": "Soren Lindqvist",
        "chef_title": "Head Roaster & Master Baker",
        "branches": [
            {
                "name": "Sanepa Roastery & Courtyard",
                "code": "NRD-SNP-01",
                "slug": "sanepa-roastery",
                "is_main_branch": True,
                "address": "Sanepa Chowk, Lalitpur",
                "city": "Lalitpur",
                "phone": "+977-1-4411223",
            },
        ],
        "dishes": [
            ("Sourdough &viennoiserie", "Swedish Braided Cardamom Bun", "320.00", "85.00", "BAKERY", True, "NONE", True),
            ("Sourdough &viennoiserie", "Twice-Baked Almond Croissant", "360.00", "95.00", "BAKERY", True, "NONE", True),
            ("Sourdough &viennoiserie", "36-Hour Country Sourdough Loaf", "480.00", "120.00", "BAKERY", True, "NONE", False),
            ("All-Day Nordic Brunch", "Smoked Salmon Smørrebrød & Dill Cream", "780.00", "260.00", "COLD_PANTRY", False, "NONE", True),
            ("All-Day Nordic Brunch", "Poached Eggs, Avocado & Chilli Sourdough", "640.00", "190.00", "HOT_KITCHEN", True, "MILD", True),
            ("All-Day Nordic Brunch", "Nordic Berry & Roasted Granola Skyr Bowl", "520.00", "150.00", "COLD_PANTRY", True, "NONE", False),
            ("All-Day Nordic Brunch", "Grilled Halloumi & Roasted Squash Tartine", "680.00", "210.00", "GRILL", True, "NONE", False),
            ("Specialty Coffee", "Panama Geisha V60 Hand Pour-Over", "450.00", "130.00", "BAR", True, "NONE", True),
            ("Specialty Coffee", "Oat Milk Honey Cinnamon Cortado", "340.00", "85.00", "BAR", True, "NONE", True),
            ("Specialty Coffee", "Cold Brew Tonic with Grapefruit Peel", "380.00", "90.00", "BAR", True, "NONE", False),
        ],
    },
]


class Command(BaseCommand):
    help = "Seeds public schema, subscription plans, and 4 complete demo restaurant tenants."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding Public Schema & Subscription Plans ==="))
        plans_by_slug = self._seed_public_schema()

        for cfg in DEMO_TENANTS:
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"=== Provisioning & Seeding Tenant: {cfg['name']} ({cfg['slug']}) ==="
                )
            )
            self._seed_restaurant_tenant(cfg, plans_by_slug)

        self.stdout.write(self.style.SUCCESS("All 4 multi-tenant restaurants and public SaaS telemetry seeded!"))

    def _seed_public_schema(self):
        with schema_context("public"):
            public_tenant, _ = Client.objects.update_or_create(
                schema_name="public",
                defaults={
                    "name": "RestoCloud SaaS Platform",
                    "slug": "public",
                    "subscription_status": Client.SubscriptionStatus.ACTIVE,
                    "is_active": True,
                    "owner_name": "Platform SuperAdmin",
                    "owner_email": "superadmin@restosaas.com",
                    "city": "Kathmandu",
                    "country": "Nepal",
                    "currency": "NPR",
                },
            )
            Domain.objects.get_or_create(
                domain="localhost",
                defaults={"tenant": public_tenant, "is_primary": True},
            )

            superadmin, created = User.objects.get_or_create(
                email="superadmin@restosaas.com",
                defaults={
                    "full_name": "Siddhartha Rajbhandari (SuperAdmin)",
                    "role": User.Role.SUPERADMIN,
                    "phone": "+977-9801000001",
                    "department": "Platform Administration",
                    "specialization": "Multi-Tenant Cloud Operations",
                    "pos_pin": "0000",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                },
            )
            superadmin.set_password("Admin@12345")
            superadmin.is_staff = True
            superadmin.is_superuser = True
            superadmin.role = User.Role.SUPERADMIN
            superadmin.save()

            plans_spec = [
                {
                    "slug": "starter",
                    "name": "Starter",
                    "description": "Ideal for independent cafés, bakeries, and single-outlet bistros.",
                    "price_monthly": Decimal("39.00"),
                    "price_yearly": Decimal("390.00"),
                    "price_monthly_npr": Decimal("3999.00"),
                    "price_yearly_npr": Decimal("39990.00"),
                    "trial_days": 14,
                    "max_branches": 1,
                    "max_staff_users": 10,
                    "max_tables": 16,
                    "max_menu_items": 80,
                    "max_monthly_orders": 2000,
                    "enable_pos": True,
                    "enable_kds": True,
                    "enable_inventory": True,
                    "enable_online_ordering": True,
                    "enable_table_reservations": True,
                    "enable_loyalty_crm": False,
                    "enable_multi_branch": False,
                    "enable_advanced_analytics": False,
                    "enable_custom_domain": False,
                    "is_featured": False,
                    "features_json": [
                        "Fast Touch POS & Thermal KOT Billing",
                        "Live Kitchen Display System (KDS)",
                        "QR Table Ordering & Digital Menu",
                        "14-Day Free Trial",
                    ],
                },
                {
                    "slug": "growth",
                    "name": "Growth",
                    "description": "Designed for high-volume restaurants, izakayas, and multi-station kitchens.",
                    "price_monthly": Decimal("89.00"),
                    "price_yearly": Decimal("890.00"),
                    "price_monthly_npr": Decimal("8999.00"),
                    "price_yearly_npr": Decimal("89990.00"),
                    "trial_days": 14,
                    "max_branches": 3,
                    "max_staff_users": 30,
                    "max_tables": 45,
                    "max_menu_items": 250,
                    "max_monthly_orders": 8000,
                    "enable_pos": True,
                    "enable_kds": True,
                    "enable_inventory": True,
                    "enable_online_ordering": True,
                    "enable_table_reservations": True,
                    "enable_loyalty_crm": True,
                    "enable_multi_branch": True,
                    "enable_advanced_analytics": True,
                    "enable_custom_domain": False,
                    "is_featured": True,
                    "features_json": [
                        "Up to 3 Restaurant Branches",
                        "Recipe Auto-Deduction & Purchase Orders",
                        "Loyalty Points, Tiers & Promo Coupons",
                        "Nepal 13% VAT + 10% Service Charge Tax Invoices",
                        "eSewa, Khalti & Fonepay Dynamic QR Checkout",
                    ],
                },
                {
                    "slug": "enterprise",
                    "name": "Enterprise",
                    "description": "Full-scale hospitality suite for flagship groups, fine-dining venues, and franchises.",
                    "price_monthly": Decimal("179.00"),
                    "price_yearly": Decimal("1790.00"),
                    "price_monthly_npr": Decimal("17999.00"),
                    "price_yearly_npr": Decimal("179990.00"),
                    "trial_days": 30,
                    "max_branches": 15,
                    "max_staff_users": 150,
                    "max_tables": 150,
                    "max_menu_items": 1000,
                    "max_monthly_orders": 50000,
                    "enable_pos": True,
                    "enable_kds": True,
                    "enable_inventory": True,
                    "enable_online_ordering": True,
                    "enable_table_reservations": True,
                    "enable_loyalty_crm": True,
                    "enable_multi_branch": True,
                    "enable_advanced_analytics": True,
                    "enable_custom_domain": True,
                    "is_featured": False,
                    "features_json": [
                        "Up to 15 Multi-City Branches",
                        "Unlimited KDS Stations & Course Pacing",
                        "Full P&L, COGS & Cash Register Reconciliation",
                        "Custom Domain & 4 Branded Website Themes",
                        "Dedicated Account Concierge & Audit Trail",
                    ],
                },
            ]

            plans_by_slug = {}
            for p_spec in plans_spec:
                slug = p_spec.pop("slug")
                plan, _ = SubscriptionPlan.objects.update_or_create(
                    slug=slug, defaults=p_spec
                )
                plans_by_slug[slug] = plan

            return plans_by_slug

    def _seed_restaurant_tenant(self, cfg, plans_by_slug):
        slug = cfg["slug"]
        schema_name = slug.replace("-", "_")
        plan = plans_by_slug.get(cfg["plan_slug"]) or plans_by_slug["growth"]

        with schema_context("public"):
            tenant, _ = Client.objects.update_or_create(
                schema_name=schema_name,
                defaults={
                    "name": cfg["name"],
                    "slug": slug,
                    "plan": plan,
                    "subscription_status": Client.SubscriptionStatus.ACTIVE,
                    "trial_ends_at": timezone.now() + timedelta(days=30),
                    "is_active": True,
                    "owner_name": cfg["owner_name"],
                    "owner_email": cfg["owner_email"],
                    "phone": cfg["phone"],
                    "city": cfg["city"],
                    "country": cfg["country"],
                    "cuisine_type": cfg["cuisine_type"],
                    "currency": cfg["currency"],
                    "pan_vat_number": cfg["pan_vat_number"],
                    "tax_system": Client.TaxSystem.VAT_13_NP,
                    "tax_rate_percent": Decimal("13.00"),
                    "service_charge_percent": Decimal("10.00"),
                    "fiscal_year": "2082/83",
                },
            )
            Domain.objects.get_or_create(
                domain=f"{slug}.localhost",
                defaults={"tenant": tenant, "is_primary": True},
            )

            gateways = [
                SubscriptionInvoice.PaymentGateway.FONEPAY,
                SubscriptionInvoice.PaymentGateway.ESEWA,
                SubscriptionInvoice.PaymentGateway.KHALTI,
                SubscriptionInvoice.PaymentGateway.STRIPE,
            ]
            gw = gateways[len(slug) % len(gateways)]
            SubscriptionInvoice.objects.update_or_create(
                invoice_number=f"SUB-2082-{slug[:4].upper()}-01",
                defaults={
                    "tenant": tenant,
                    "plan": plan,
                    "billing_cycle": SubscriptionInvoice.BillingCycle.MONTHLY,
                    "amount": plan.price_monthly,
                    "currency": "USD",
                    "payment_gateway": gw,
                    "status": SubscriptionInvoice.Status.PAID,
                    "period_start": date.today() - timedelta(days=15),
                    "period_end": date.today() + timedelta(days=15),
                },
            )

        with schema_context(tenant.schema_name):
            # 1. Branches
            branches = []
            for b_cfg in cfg["branches"]:
                b_obj, _ = Branch.objects.update_or_create(
                    slug=b_cfg["slug"],
                    defaults={
                        "name": b_cfg["name"],
                        "code": b_cfg["code"],
                        "is_main_branch": b_cfg["is_main_branch"],
                        "address": b_cfg["address"],
                        "city": b_cfg["city"],
                        "phone": b_cfg["phone"],
                        "email": cfg["owner_email"],
                        "manager_name": cfg["owner_name"],
                        "pan_vat_number": cfg["pan_vat_number"],
                        "tax_rate_percent": Decimal("13.00"),
                        "service_charge_percent": Decimal("10.00"),
                        "receipt_header": f"{cfg['name']} — {b_cfg['name']}",
                        "receipt_footer": f"PAN/VAT: {cfg['pan_vat_number']} | Thank you for dining at {cfg['name']}!",
                    },
                )
                branches.append(b_obj)
            main_branch = branches[0]
            second_branch = branches[1] if len(branches) > 1 else main_branch

            # 2. Staff Users across all roles with POS PINs
            domain_part = cfg["owner_email"].split("@")[1]
            staff_specs = [
                (
                    cfg["owner_email"],
                    cfg["owner_name"],
                    User.Role.RESTAURANT_ADMIN,
                    "Executive Management",
                    "Restaurant Operations & Strategy",
                    "1111",
                    main_branch,
                ),
                (
                    f"manager@{domain_part}",
                    "Roshan Shrestha",
                    User.Role.MANAGER,
                    "Floor Operations",
                    "Hospitality & Guest Experience",
                    "2222",
                    main_branch,
                ),
                (
                    f"cashier@{domain_part}",
                    "Sabina Maharjan",
                    User.Role.CASHIER,
                    "POS & Billing",
                    "Cash Register & Tax Invoices",
                    "3333",
                    main_branch,
                ),
                (
                    f"waiter@{domain_part}",
                    "Bikash Gurung",
                    User.Role.WAITER,
                    "Dining Floor",
                    "Table Service & Course Pacing",
                    "4444",
                    main_branch,
                ),
                (
                    f"chef@{domain_part}",
                    cfg["chef_name"],
                    User.Role.CHEF,
                    "Culinary Kitchen",
                    cfg["chef_title"],
                    "5555",
                    main_branch,
                ),
                (
                    f"delivery@{domain_part}",
                    "Niraj Tamang",
                    User.Role.DELIVERY,
                    "Dispatch & Delivery",
                    "Express City Delivery",
                    "6666",
                    second_branch,
                ),
            ]
            staff_objs = {}
            for email, full_name, role, dept, spec, pin, br in staff_specs:
                u, _ = User.objects.update_or_create(
                    email=email,
                    defaults={
                        "full_name": full_name,
                        "role": role,
                        "phone": cfg["phone"],
                        "department": dept,
                        "specialization": spec,
                        "branch": br,
                        "pos_pin": pin,
                        "is_public_staff": role != User.Role.DELIVERY,
                        "is_active": True,
                        "is_staff": role in (User.Role.RESTAURANT_ADMIN, User.Role.MANAGER),
                    },
                )
                u.set_password("Admin@12345")
                u.save()
                staff_objs[role] = u

            # 3. StaffShifts
            today = timezone.now().date()
            shift_specs = [
                (staff_objs[User.Role.MANAGER], "MANAGER", time(9, 0), time(18, 0), "FLOOR_MAIN", StaffShift.Status.CHECKED_IN),
                (staff_objs[User.Role.CASHIER], "CASHIER", time(10, 0), time(20, 0), "POS_COUNTER_1", StaffShift.Status.CHECKED_IN),
                (staff_objs[User.Role.WAITER], "WAITER", time(11, 0), time(22, 0), "PATIO_HALL", StaffShift.Status.CHECKED_IN),
                (staff_objs[User.Role.CHEF], "CHEF", time(9, 30), time(21, 30), "HOT_KITCHEN", StaffShift.Status.CHECKED_IN),
                (staff_objs[User.Role.DELIVERY], "DELIVERY", time(12, 0), time(22, 0), "DELIVERY_DISPATCH", StaffShift.Status.SCHEDULED),
            ]
            for st_user, r_shift, s_time, e_time, station, st_status in shift_specs:
                StaffShift.objects.update_or_create(
                    staff=st_user,
                    shift_date=today,
                    defaults={
                        "branch": st_user.branch,
                        "role_on_shift": r_shift,
                        "start_time": s_time,
                        "end_time": e_time,
                        "station": station,
                        "status": st_status,
                        "clock_in_at": (
                            timezone.now() - timedelta(hours=3)
                            if st_status == StaffShift.Status.CHECKED_IN
                            else None
                        ),
                    },
                )

            # 4. Menu Categories & Subcategories & Dishes
            cat_map = {}
            order_idx = 1
            for dish_tuple in cfg["dishes"]:
                cat_name = dish_tuple[0]
                if cat_name not in cat_map:
                    c_obj, _ = MenuCategory.objects.update_or_create(
                        name=cat_name,
                        defaults={
                            "description": f"Curated {cat_name.lower()} prepared fresh daily",
                            "display_order": order_idx,
                            "is_active": True,
                        },
                    )
                    cat_map[cat_name] = c_obj
                    order_idx += 1

            # Create one subcategory to demonstrate parent-child hierarchy
            first_cat = list(cat_map.values())[0]
            MenuCategory.objects.update_or_create(
                name=f"Chef's Reserve {first_cat.name}",
                defaults={
                    "parent": first_cat,
                    "description": "Limited daily small-batch chef selections",
                    "display_order": 99,
                    "is_active": True,
                },
            )

            menu_items = []
            for (
                cat_name,
                item_name,
                price_str,
                cost_str,
                station,
                is_veg,
                spice,
                featured,
            ) in cfg["dishes"]:
                mi, _ = MenuItem.objects.update_or_create(
                    name=item_name,
                    defaults={
                        "category": cat_map[cat_name],
                        "description": f"House signature {item_name.lower()} crafted with seasonal ingredients.",
                        "price": Decimal(price_str),
                        "cost_price": Decimal(cost_str),
                        "prep_time_minutes": 14 if station != "BAR" else 5,
                        "kitchen_station": station,
                        "is_vegetarian": is_veg,
                        "is_vegan": is_veg and station == "BAR",
                        "spice_level": spice,
                        "is_available": True,
                        "is_featured": featured,
                        "variants_json": [
                            {"name": "Regular", "price": 0},
                            {"name": "Large / Sharing", "price": 180},
                        ],
                        "modifiers_json": [
                            {"name": "Extra House Sauce", "price": 60},
                            {"name": "Add Organic Egg / Cheese", "price": 90},
                        ],
                    },
                )
                menu_items.append(mi)

            # 5. Dining Zones & 12 Tables
            zone_main, _ = DiningZone.objects.update_or_create(
                code="FLOOR-1",
                defaults={
                    "branch": main_branch,
                    "name": "Main Hearth Dining Room",
                    "floor_number": 1,
                    "is_active": True,
                },
            )
            zone_terrace, _ = DiningZone.objects.update_or_create(
                code="COURTYARD-2",
                defaults={
                    "branch": main_branch,
                    "name": "Garden Courtyard & Terrace",
                    "floor_number": 2,
                    "is_active": True,
                },
            )
            zone_vip, _ = DiningZone.objects.update_or_create(
                code="VIP-LOUNGE",
                defaults={
                    "branch": second_branch,
                    "name": "Private Chef's Salon",
                    "floor_number": 3,
                    "is_active": True,
                },
            )

            tables = []
            for idx in range(1, 13):
                if idx <= 6:
                    z = zone_main
                elif idx <= 10:
                    z = zone_terrace
                else:
                    z = zone_vip
                t_status = DiningTable.Status.AVAILABLE
                guests = 0
                if idx in (1, 2, 5):
                    t_status = DiningTable.Status.OCCUPIED
                    guests = 4
                elif idx == 7:
                    t_status = DiningTable.Status.RESERVED
                    guests = 6
                elif idx == 8:
                    t_status = DiningTable.Status.BILL_PRINTED
                    guests = 2

                t_obj, _ = DiningTable.objects.update_or_create(
                    table_number=f"T-{idx:02d}",
                    defaults={
                        "branch": z.branch,
                        "zone": z,
                        "capacity": 2 if idx % 3 == 0 else (6 if idx >= 9 else 4),
                        "shape": (
                            DiningTable.Shape.ROUND
                            if idx % 3 == 0
                            else (
                                DiningTable.Shape.BOOTH
                                if idx >= 9
                                else DiningTable.Shape.SQUARE
                            )
                        ),
                        "status": t_status,
                        "current_guest_count": guests,
                        "pos_x": ((idx - 1) % 4) * 180 + 40,
                        "pos_y": ((idx - 1) // 4) * 150 + 40,
                    },
                )
                tables.append(t_obj)

            # 6. Suppliers, Inventory Items (including low-stock), Recipes & Purchase Orders
            sup1, _ = Supplier.objects.update_or_create(
                name="Himalayan Organic Farms & Butchery",
                defaults={
                    "contact_person": "Dipak Karki",
                    "phone": "+977-9851022334",
                    "email": "orders@himalayanfarms.com.np",
                    "address": "Kalimati Wholesale Market, Kathmandu",
                    "pan_number": "304911223",
                    "category": "Meat & Fresh Produce",
                },
            )
            sup2, _ = Supplier.objects.update_or_create(
                name="Valley Artisan Dairy & Specialty Imports",
                defaults={
                    "contact_person": "Anita Joshi",
                    "phone": "+977-9841099887",
                    "email": "supply@valleydairy.com.np",
                    "address": "Balaju Industrial Area, Kathmandu",
                    "pan_number": "305899112",
                    "category": "Dairy, Dry Goods & Beverages",
                },
            )

            inv_specs = [
                ("INV-MEAT-01", "Prime Minced Buff / Artisan Protein", InventoryItem.Category.MEAT_SEAFOOD, "kg", "18.500", "8.000", "680.00", sup1),
                ("INV-FLOUR-02", "Organic Stone-Ground Wheat & Buckwheat Flour", InventoryItem.Category.DRY_GOODS, "kg", "42.000", "12.000", "140.00", sup2),
                ("INV-SPICE-03", "Mustang Timur & Himalayan Herb Blend", InventoryItem.Category.DRY_GOODS, "kg", "1.800", "3.000", "1450.00", sup1),  # Low stock!
                ("INV-DAIRY-04", "Cultured Artisan Butter & Cream", InventoryItem.Category.DAIRY, "kg", "3.200", "5.000", "920.00", sup2),  # Low stock!
                ("INV-PROD-05", "Organic Gundruk, Garlic & Mountain Greens", InventoryItem.Category.PRODUCE, "kg", "14.000", "6.000", "240.00", sup1),
                ("INV-BEV-06", "Single-Origin Ilam Tea & Craft Syrup Base", InventoryItem.Category.BEVERAGES, "ltr", "11.500", "4.000", "480.00", sup2),
            ]
            inv_items = []
            for sku, i_name, cat, unit, cur_stk, reord, cost, sup in inv_specs:
                inv_obj, _ = InventoryItem.objects.update_or_create(
                    sku=sku,
                    defaults={
                        "branch": main_branch,
                        "name": i_name,
                        "category": cat,
                        "unit": unit,
                        "current_stock": Decimal(cur_stk),
                        "reorder_level": Decimal(reord),
                        "cost_per_unit": Decimal(cost),
                        "supplier": sup,
                    },
                )
                inv_items.append(inv_obj)

            # Link recipes for top menu items
            if menu_items and inv_items:
                RecipeIngredient.objects.update_or_create(
                    menu_item=menu_items[0],
                    inventory_item=inv_items[0],
                    defaults={"quantity_required": Decimal("0.220"), "unit_note": "220g protein per portion"},
                )
                RecipeIngredient.objects.update_or_create(
                    menu_item=menu_items[0],
                    inventory_item=inv_items[1],
                    defaults={"quantity_required": Decimal("0.120"), "unit_note": "120g dough wrapper"},
                )
                RecipeIngredient.objects.update_or_create(
                    menu_item=menu_items[4],
                    inventory_item=inv_items[0],
                    defaults={"quantity_required": Decimal("0.300"), "unit_note": "300g main cut"},
                )

            po, _ = PurchaseOrder.objects.update_or_create(
                po_number=f"PO-2082-{slug[:3].upper()}-001",
                defaults={
                    "branch": main_branch,
                    "supplier": sup1,
                    "status": PurchaseOrder.Status.ORDERED,
                    "total_amount": Decimal("18450.00"),
                    "expected_date": today + timedelta(days=2),
                    "notes": "Weekly fresh mountain produce & spice restock",
                },
            )
            PurchaseOrderItem.objects.update_or_create(
                purchase_order=po,
                inventory_item=inv_items[2],
                defaults={
                    "quantity_ordered": Decimal("6.000"),
                    "quantity_received": Decimal("0.000"),
                    "unit_cost": inv_items[2].cost_per_unit,
                },
            )

            # 7. Customers, Coupons & Feedback
            cust_specs = [
                ("Prashant Adhikari", "+977-9801122334", "prashant@example.com", Customer.Tier.PLATINUM, 3120, 4200, "48500.00", 18),
                ("Shristi Rana", "+977-9841223344", "shristi@example.com", Customer.Tier.GOLD, 1450, 1890, "24600.00", 11),
                ("Anुपम Koirala", "+977-9851055667", "anupam@example.com", Customer.Tier.SILVER, 520, 680, "9800.00", 5),
                ("Elena Rostova", "+977-9818009988", "elena@example.com", Customer.Tier.BRONZE, 180, 180, "3400.00", 2),
            ]
            customers = []
            for c_name, c_phone, c_email, tier, pts, life_pts, spent, visits in cust_specs:
                c_obj, _ = Customer.objects.update_or_create(
                    phone=c_phone,
                    defaults={
                        "full_name": c_name,
                        "email": c_email,
                        "tier": tier,
                        "loyalty_points": pts,
                        "lifetime_points": life_pts,
                        "total_spent": Decimal(spent),
                        "visits_count": visits,
                    },
                )
                customers.append(c_obj)

            coupons_spec = [
                ("NEPAL20", "Festival 20% Off Dining Deal", Coupon.DiscountType.PERCENTAGE, "20.00", "1000.00", "600.00"),
                ("WELCOME10", "First Online Order 10% Welcome", Coupon.DiscountType.PERCENTAGE, "10.00", "500.00", "350.00"),
                ("FEAST500", "Flat NPR 500 Off Family Feast", Coupon.DiscountType.FIXED, "500.00", "2500.00", "500.00"),
            ]
            for c_code, c_title, c_type, c_val, min_ord, max_disc in coupons_spec:
                Coupon.objects.update_or_create(
                    code=c_code,
                    defaults={
                        "title": c_title,
                        "discount_type": c_type,
                        "discount_value": Decimal(c_val),
                        "min_order_amount": Decimal(min_ord),
                        "max_discount_amount": Decimal(max_disc),
                        "valid_from": today - timedelta(days=30),
                        "valid_until": today + timedelta(days=90),
                        "usage_limit": 500,
                        "used_count": 14,
                        "is_active": True,
                    },
                )

            CustomerFeedback.objects.update_or_create(
                guest_name="Prashant Adhikari",
                order_number=f"ORD-{slug[:3].upper()}-101",
                defaults={
                    "customer": customers[0],
                    "food_rating": 5,
                    "service_rating": 5,
                    "ambience_rating": 5,
                    "overall_rating": 5,
                    "comment": f"Unmatched flavors at {cfg['name']}! The table QR ordering and warm hospitality were flawless.",
                    "is_public": True,
                },
            )

            # 8. CashRegisterSessions & Expenses
            CashRegisterSession.objects.update_or_create(
                register_name="Main POS Register #1",
                status=CashRegisterSession.Status.OPEN,
                defaults={
                    "branch": main_branch,
                    "opened_by": staff_objs[User.Role.CASHIER],
                    "opening_float": Decimal("10000.00"),
                    "cash_sales": Decimal("14580.00"),
                    "card_sales": Decimal("9420.00"),
                    "digital_wallet_sales": Decimal("18650.00"),
                    "cash_in": Decimal("2000.00"),
                    "cash_out": Decimal("850.00"),
                    "notes": "Morning & Evening active POS register session",
                },
            )

            Expense.objects.update_or_create(
                title="Weekly Fresh Valley Produce & Herbs Settlement",
                defaults={
                    "branch": main_branch,
                    "category": Expense.Category.INGREDIENTS,
                    "vendor_name": sup1.name,
                    "amount": Decimal("2400.00"),
                    "payment_method": "FONEPAY",
                    "reference_number": "EXP-2082-019",
                    "expense_date": today - timedelta(days=1),
                    "recorded_by": staff_objs[User.Role.MANAGER],
                },
            )
            Expense.objects.update_or_create(
                title="Commercial Kitchen Gas & Electricity Utility",
                defaults={
                    "branch": main_branch,
                    "category": Expense.Category.UTILITIES,
                    "vendor_name": "Nepal Electricity & Gas Co.",
                    "amount": Decimal("1800.00"),
                    "payment_method": "ESEWA",
                    "reference_number": "EXP-2082-020",
                    "expense_date": today,
                    "recorded_by": staff_objs[User.Role.MANAGER],
                },
            )

            # 9. Orders, KOT Items, PaymentTransactions & Sequential TaxInvoices
            prefix = slug[:3].upper()
            orders_spec = [
                (
                    f"ORD-{prefix}-101",
                    Order.OrderType.DINE_IN,
                    Order.Channel.POS,
                    Order.Status.COMPLETED,
                    Order.PaymentStatus.PAID,
                    Order.PaymentMethod.FONEPAY,
                    tables[2],
                    customers[0],
                    "Prashant Adhikari",
                    "+977-9801122334",
                    "601239981",
                    [(menu_items[0], 2, OrderItem.KotStatus.SERVED), (menu_items[4], 2, OrderItem.KotStatus.SERVED)],
                    main_branch,
                ),
                (
                    f"ORD-{prefix}-102",
                    Order.OrderType.DINE_IN,
                    Order.Channel.POS,
                    Order.Status.COMPLETED,
                    Order.PaymentStatus.PAID,
                    Order.PaymentMethod.ESEWA,
                    tables[3],
                    customers[1],
                    "Shristi Rana",
                    "+977-9841223344",
                    "",
                    [(menu_items[1], 1, OrderItem.KotStatus.SERVED), (menu_items[5], 2, OrderItem.KotStatus.SERVED)],
                    second_branch,
                ),
                (
                    f"ORD-{prefix}-103",
                    Order.OrderType.DINE_IN,
                    Order.Channel.WAITER,
                    Order.Status.IN_KITCHEN,
                    Order.PaymentStatus.UNPAID,
                    Order.PaymentMethod.CASH,
                    tables[0],
                    customers[2],
                    "Anupam Koirala",
                    "+977-9851055667",
                    "",
                    [(menu_items[0], 2, OrderItem.KotStatus.PREPARING), (menu_items[4], 1, OrderItem.KotStatus.QUEUED)],
                    main_branch,
                ),
                (
                    f"ORD-{prefix}-104",
                    Order.OrderType.QR_ORDER,
                    Order.Channel.QR_MENU,
                    Order.Status.READY,
                    Order.PaymentStatus.UNPAID,
                    Order.PaymentMethod.KHALTI,
                    tables[1],
                    None,
                    "Table T-02 QR Guest",
                    "+977-9801998877",
                    "",
                    [(menu_items[2], 1, OrderItem.KotStatus.READY), (menu_items[8], 2, OrderItem.KotStatus.READY)],
                    main_branch,
                ),
                (
                    f"ORD-{prefix}-105",
                    Order.OrderType.DELIVERY,
                    Order.Channel.WEBSITE,
                    Order.Status.IN_KITCHEN,
                    Order.PaymentStatus.PAID,
                    Order.PaymentMethod.ESEWA,
                    None,
                    customers[3],
                    "Elena Rostova",
                    "+977-9818009988",
                    "",
                    [(menu_items[4], 2, OrderItem.KotStatus.PREPARING), (menu_items[9], 2, OrderItem.KotStatus.QUEUED)],
                    main_branch,
                ),
            ]

            for (
                ord_num,
                o_type,
                chan,
                o_status,
                p_status,
                p_method,
                tbl,
                cust,
                c_name,
                c_phone,
                c_pan,
                item_tuples,
                br,
            ) in orders_spec:
                ord_obj, _ = Order.objects.update_or_create(
                    order_number=ord_num,
                    defaults={
                        "branch": br,
                        "order_type": o_type,
                        "channel": chan,
                        "status": o_status,
                        "payment_status": p_status,
                        "payment_method": p_method,
                        "table": tbl if o_status != Order.Status.COMPLETED else None,
                        "waiter": staff_objs[User.Role.WAITER],
                        "cashier": staff_objs[User.Role.CASHIER],
                        "customer": cust,
                        "customer_name": c_name,
                        "customer_phone": c_phone,
                        "customer_pan": c_pan,
                        "guest_count": 3,
                        "completed_at": (
                            timezone.now() - timedelta(minutes=45)
                            if o_status == Order.Status.COMPLETED
                            else None
                        ),
                    },
                )
                ord_obj.items.all().delete()
                for m_item, qty, k_status in item_tuples:
                    OrderItem.objects.create(
                        order=ord_obj,
                        menu_item=m_item,
                        item_name=m_item.name,
                        variant_name="Regular",
                        kitchen_station=m_item.kitchen_station,
                        quantity=qty,
                        unit_price=m_item.price,
                        kot_batch=1,
                        kot_status=k_status,
                        is_stock_deducted=(k_status in (OrderItem.KotStatus.READY, OrderItem.KotStatus.SERVED)),
                    )
                ord_obj.recalculate_totals(tenant=tenant)

                if p_status == Order.PaymentStatus.PAID:
                    ord_obj.payments.all().delete()
                    PaymentTransaction.objects.create(
                        order=ord_obj,
                        amount=ord_obj.total_amount,
                        method=p_method,
                        reference=f"{p_method}-{ord_num}",
                        paid_by_label=c_name,
                        gateway_status="SUCCESS",
                    )
                    if not ord_obj.tax_invoice.exists():
                        inv_num = TaxInvoice.generate_next_invoice_number(
                            fiscal_year=tenant.fiscal_year
                        )
                        TaxInvoice.objects.create(
                            branch=br,
                            order=ord_obj,
                            invoice_number=inv_num,
                            fiscal_year=tenant.fiscal_year,
                            seller_pan=tenant.pan_vat_number,
                            customer_name=c_name,
                            customer_pan=c_pan,
                            subtotal=ord_obj.subtotal,
                            discount_amount=ord_obj.discount_amount,
                            service_charge=ord_obj.service_charge,
                            taxable_amount=ord_obj.subtotal - ord_obj.discount_amount + ord_obj.service_charge,
                            tax_rate_percent=tenant.tax_rate_percent,
                            tax_amount=ord_obj.tax_amount,
                            grand_total=ord_obj.total_amount,
                            payment_method=p_method,
                            issued_by_name=staff_objs[User.Role.CASHIER].full_name,
                        )

            # 10. Table Reservations
            TableReservation.objects.update_or_create(
                reservation_code=f"RES-{prefix}-01",
                defaults={
                    "branch": main_branch,
                    "customer": customers[0],
                    "guest_name": "Prashant Adhikari",
                    "guest_phone": "+977-9801122334",
                    "guest_email": "prashant@example.com",
                    "party_size": 6,
                    "reservation_date": today,
                    "reservation_time": time(19, 30),
                    "duration_minutes": 120,
                    "table": tables[6],
                    "status": TableReservation.Status.CONFIRMED,
                    "occasion": TableReservation.Occasion.ANNIVERSARY,
                    "special_requests": "Window or courtyard table with candlelit setting.",
                },
            )
            TableReservation.objects.update_or_create(
                reservation_code=f"RES-{prefix}-02",
                defaults={
                    "branch": main_branch,
                    "customer": customers[1],
                    "guest_name": "Shristi Rana",
                    "guest_phone": "+977-9841223344",
                    "guest_email": "shristi@example.com",
                    "party_size": 4,
                    "reservation_date": today,
                    "reservation_time": time(20, 15),
                    "duration_minutes": 90,
                    "table": tables[8],
                    "status": TableReservation.Status.WAITLIST,
                    "occasion": TableReservation.Occasion.BIRTHDAY,
                    "special_requests": "Complimentary birthday dessert candle please.",
                },
            )

            # 11. Notifications & AuditLogs
            Notification.objects.update_or_create(
                title=f"Low Stock Alert: {inv_items[2].name}",
                defaults={
                    "branch": main_branch,
                    "category": Notification.Category.LOW_STOCK,
                    "severity": Notification.Severity.WARNING,
                    "message": f"{inv_items[2].name} is at {inv_items[2].current_stock} {inv_items[2].unit} (below {inv_items[2].reorder_level} {inv_items[2].unit}).",
                    "action_url": "/dashboard/inventory",
                    "is_read": False,
                },
            )
            Notification.objects.update_or_create(
                title=f"Order ORD-{prefix}-104 Ready at Pass",
                defaults={
                    "branch": main_branch,
                    "category": Notification.Category.KDS_READY,
                    "severity": Notification.Severity.SUCCESS,
                    "message": "Table T-02 QR order is plated and ready for service.",
                    "action_url": "/dashboard/kds",
                    "is_read": False,
                },
            )

            AuditLog.objects.update_or_create(
                action=AuditLog.Action.REGISTER_OPENED,
                target_id="1",
                defaults={
                    "actor": staff_objs[User.Role.CASHIER],
                    "actor_name": staff_objs[User.Role.CASHIER].full_name,
                    "branch": main_branch,
                    "target_model": "CashRegisterSession",
                    "description": "Opened Main POS Register #1 with NPR 10,000.00 float.",
                },
            )

            # 12. Website Settings & Testimonials
            ws = RestaurantWebsiteSettings.objects.first()
            if not ws:
                ws = RestaurantWebsiteSettings.objects.create()
            ws.theme_id = cfg["theme_id"]
            ws.color_palette = cfg["color_palette"]
            ws.tagline = cfg["tagline"]
            ws.hero_title = cfg["hero_title"]
            ws.hero_subtitle = cfg["hero_subtitle"]
            ws.chef_name = cfg["chef_name"]
            ws.chef_title = cfg["chef_title"]
            ws.address = main_branch.address
            ws.phone = cfg["phone"]
            ws.email = cfg["owner_email"]
            ws.highlights_json = [
                {"label": "Signature Style", "value": cfg["cuisine_type"]},
                {"label": "Avg Prep Time", "value": "14 mins"},
                {"label": "Guest Rating", "value": "4.9 / 5.0"},
            ]
            ws.save()

            Testimonial.objects.update_or_create(
                guest_name="Aayushma Sharma",
                defaults={
                    "guest_role": "Food Critic & Travel Writer",
                    "rating": 5,
                    "comment": f"Every visit to {cfg['name']} feels extraordinary. The balance of flavors and seamless table hospitality set the benchmark in {cfg['city']}.",
                    "dish_ordered": menu_items[0].name,
                    "is_featured": True,
                },
            )
            Testimonial.objects.update_or_create(
                guest_name="Marcus Vance",
                defaults={
                    "guest_role": "Hospitality Consultant",
                    "rating": 5,
                    "comment": f"Ordered straight from our table QR code and watched live kitchen updates. Incredible culinary craft at {cfg['name']}!",
                    "dish_ordered": menu_items[4].name,
                    "is_featured": True,
                },
            )
