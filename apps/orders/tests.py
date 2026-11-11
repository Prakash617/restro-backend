from decimal import Decimal
from django.test import Client as HttpClient, TestCase
from django_tenants.utils import schema_context

from apps.accounts.models import User
from apps.accounts.views import generate_tokens_for_user
from apps.branches.models import Branch
from apps.customers.models import Customer
from apps.finance.models import CashRegisterSession, TaxInvoice
from apps.inventory.models import InventoryItem, RecipeIngredient, StockMovement
from apps.menu.models import MenuCategory, MenuItem
from apps.orders.models import Order, OrderItem
from apps.tables.models import DiningTable, DiningZone
from apps.tenants.models import Client, Domain, SubscriptionPlan


class RestaurantMultiTenantPOSAndOrdersTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with schema_context("public"):
            cls.plan, _ = SubscriptionPlan.objects.get_or_create(
                slug="test-enterprise",
                defaults={
                    "name": "Test Enterprise",
                    "price_monthly": Decimal("179.00"),
                    "price_yearly": Decimal("1790.00"),
                    "max_branches": 10,
                    "max_staff_users": 50,
                    "max_tables": 50,
                    "max_menu_items": 200,
                },
            )
            cls.public_tenant, _ = Client.objects.get_or_create(
                schema_name="public",
                defaults={
                    "name": "RestoCloud Platform",
                    "slug": "public",
                    "subscription_status": Client.SubscriptionStatus.ACTIVE,
                    "is_active": True,
                },
            )
            Domain.objects.get_or_create(
                domain="localhost",
                defaults={"tenant": cls.public_tenant, "is_primary": True},
            )

            cls.tenant_a, _ = Client.objects.get_or_create(
                schema_name="hearth_test",
                defaults={
                    "name": "Hearth Test Restaurant",
                    "slug": "hearth-test",
                    "plan": cls.plan,
                    "subscription_status": Client.SubscriptionStatus.ACTIVE,
                    "is_active": True,
                    "currency": "NPR",
                    "pan_vat_number": "609812345",
                    "tax_rate_percent": Decimal("13.00"),
                    "service_charge_percent": Decimal("10.00"),
                    "fiscal_year": "2082/83",
                },
            )
            Domain.objects.get_or_create(
                domain="hearth-test.localhost",
                defaults={"tenant": cls.tenant_a, "is_primary": True},
            )

            cls.tenant_b, _ = Client.objects.get_or_create(
                schema_name="ramen_test",
                defaults={
                    "name": "Ramen Test Restaurant",
                    "slug": "ramen-test",
                    "plan": cls.plan,
                    "subscription_status": Client.SubscriptionStatus.ACTIVE,
                    "is_active": True,
                    "currency": "NPR",
                    "pan_vat_number": "609899999",
                    "tax_rate_percent": Decimal("13.00"),
                    "service_charge_percent": Decimal("10.00"),
                    "fiscal_year": "2082/83",
                },
            )
            Domain.objects.get_or_create(
                domain="ramen-test.localhost",
                defaults={"tenant": cls.tenant_b, "is_primary": True},
            )

    def setUp(self):
        self.http = HttpClient()

        with schema_context("hearth_test"):
            self.branch_a, _ = Branch.objects.get_or_create(
                slug="thamel-main",
                defaults={
                    "name": "Thamel Main Branch",
                    "code": "KTM-01",
                    "is_main_branch": True,
                    "pan_vat_number": "609812345",
                    "tax_rate_percent": Decimal("13.00"),
                    "service_charge_percent": Decimal("10.00"),
                },
            )
            self.admin_a, _ = User.objects.get_or_create(
                email="admin@hearthtest.com",
                defaults={
                    "full_name": "Hearth Cashier Admin",
                    "role": User.Role.RESTAURANT_ADMIN,
                    "branch": self.branch_a,
                    "pos_pin": "1111",
                    "is_active": True,
                },
            )
            self.admin_a.set_password("Admin@12345")
            self.admin_a.save()
            self.token_a = generate_tokens_for_user(
                self.admin_a, tenant_slug="hearth-test"
            )["access"]

            self.cat_a, _ = MenuCategory.objects.get_or_create(
                slug="momos-grill",
                defaults={"name": "Momos & Grill", "display_order": 1},
            )
            self.dish_a, _ = MenuItem.objects.get_or_create(
                slug="jhol-momo-platter",
                defaults={
                    "category": self.cat_a,
                    "name": "Jhol Momo Platter",
                    "price": Decimal("500.00"),
                    "cost_price": Decimal("160.00"),
                    "kitchen_station": MenuItem.KitchenStation.HOT_KITCHEN,
                },
            )

        with schema_context("ramen_test"):
            self.admin_b, _ = User.objects.get_or_create(
                email="admin@ramentest.com",
                defaults={
                    "full_name": "Ramen Admin",
                    "role": User.Role.RESTAURANT_ADMIN,
                    "pos_pin": "2222",
                    "is_active": True,
                },
            )
            self.admin_b.set_password("Admin@12345")
            self.admin_b.save()
            self.token_b = generate_tokens_for_user(
                self.admin_b, tenant_slug="ramen-test"
            )["access"]

    def test_schema_isolation_and_suspended_tenant_403(self):
        """Verify strict PostgreSQL schema isolation and HTTP 403 TENANT_SUSPENDED enforcement."""
        with schema_context("hearth_test"):
            self.assertEqual(MenuItem.objects.filter(slug="jhol-momo-platter").count(), 1)

        with schema_context("ramen_test"):
            self.assertEqual(MenuItem.objects.filter(slug="jhol-momo-platter").count(), 0)

        # Suspend ramen_test and verify 403 TENANT_SUSPENDED
        with schema_context("public"):
            self.tenant_b.subscription_status = Client.SubscriptionStatus.SUSPENDED
            self.tenant_b.is_active = False
            self.tenant_b.save(update_fields=["subscription_status", "is_active"])

        res = self.http.get(
            "/api/v1/menu/items/",
            HTTP_X_TENANT_SLUG="ramen-test",
            HTTP_AUTHORIZATION=f"Bearer {self.token_b}",
        )
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.json().get("code"), "TENANT_SUSPENDED")

        # Restore status
        with schema_context("public"):
            self.tenant_b.subscription_status = Client.SubscriptionStatus.ACTIVE
            self.tenant_b.is_active = True
            self.tenant_b.save(update_fields=["subscription_status", "is_active"])

    def test_nepal_vat_13_and_service_charge_10_calculation(self):
        """
        Verify Nepal 10% Service Charge + 13% VAT calculation:
        Subtotal = 2 x 500.00 = 1000.00
        Service Charge (10%) = 100.00
        Taxable Amount = 1100.00
        VAT (13% of 1100.00) = 143.00
        Grand Total = 1243.00
        """
        with schema_context("hearth_test"):
            order = Order.objects.create(
                branch=self.branch_a,
                order_type=Order.OrderType.DINE_IN,
                customer_name="bikram@example.com",
            )
            OrderItem.objects.create(
                order=order,
                menu_item=self.dish_a,
                item_name=self.dish_a.name,
                quantity=2,
                unit_price=Decimal("500.00"),
            )
            order.recalculate_totals(tenant=self.tenant_a)

            self.assertEqual(order.subtotal, Decimal("1000.00"))
            self.assertEqual(order.service_charge, Decimal("100.00"))
            self.assertEqual(order.tax_amount, Decimal("143.00"))
            self.assertEqual(order.total_amount, Decimal("1243.00"))
            self.assertEqual(order.loyalty_points_earned, 12)

    def test_recipe_stock_auto_deduction_on_kds_bump(self):
        """Verify RecipeIngredient stock is automatically deducted once when bumped to READY."""
        with schema_context("hearth_test"):
            inv_item = InventoryItem.objects.create(
                branch=self.branch_a,
                sku="BUFF-MINCE-TEST",
                name="Test Minced Buff",
                category=InventoryItem.Category.MEAT_SEAFOOD,
                unit="kg",
                current_stock=Decimal("10.000"),
                reorder_level=Decimal("2.000"),
                cost_per_unit=Decimal("650.00"),
            )
            RecipeIngredient.objects.create(
                menu_item=self.dish_a,
                inventory_item=inv_item,
                quantity_required=Decimal("0.250"),
            )
            order = Order.objects.create(
                branch=self.branch_a,
                order_type=Order.OrderType.DINE_IN,
            )
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=self.dish_a,
                item_name=self.dish_a.name,
                quantity=4,
                unit_price=Decimal("500.00"),
                kot_status=OrderItem.KotStatus.PREPARING,
            )

        # Bump item to READY via KDS endpoint (4 x 0.250 kg = 1.000 kg deducted -> 9.000 kg left)
        res = self.http.post(
            f"/api/v1/orders/items/{order_item.id}/bump/",
            data={"kot_status": "READY"},
            content_type="application/json",
            HTTP_X_TENANT_SLUG="hearth-test",
            HTTP_AUTHORIZATION=f"Bearer {self.token_a}",
        )
        self.assertEqual(res.status_code, 200)

        with schema_context("hearth_test"):
            inv_item.refresh_from_db()
            order_item.refresh_from_db()
            self.assertTrue(order_item.is_stock_deducted)
            self.assertEqual(inv_item.current_stock, Decimal("9.000"))
            self.assertTrue(
                StockMovement.objects.filter(
                    item=inv_item,
                    movement_type=StockMovement.MovementType.CONSUMPTION,
                ).exists()
            )

        # Bump again to SERVED and verify idempotency (no second deduction)
        res2 = self.http.post(
            f"/api/v1/orders/items/{order_item.id}/bump/",
            data={"kot_status": "SERVED"},
            content_type="application/json",
            HTTP_X_TENANT_SLUG="hearth-test",
            HTTP_AUTHORIZATION=f"Bearer {self.token_a}",
        )
        self.assertEqual(res2.status_code, 200)
        with schema_context("hearth_test"):
            inv_item.refresh_from_db()
            self.assertEqual(inv_item.current_stock, Decimal("9.000"))

    def test_pos_checkout_tax_invoice_register_and_table_release(self):
        """Verify POS checkout settles order, issues sequential TaxInvoice, updates register & frees table."""
        with schema_context("hearth_test"):
            zone = DiningZone.objects.create(
                branch=self.branch_a, name="Test Hall", code="TH-1", floor_number=1
            )
            table = DiningTable.objects.create(
                branch=self.branch_a,
                zone=zone,
                table_number="T-99",
                status=DiningTable.Status.OCCUPIED,
                current_guest_count=4,
            )
            customer = Customer.objects.create(
                full_name="Sita Sharma",
                phone="+977-9801112233",
                loyalty_points=50,
                lifetime_points=50,
            )
            register = CashRegisterSession.objects.create(
                branch=self.branch_a,
                opened_by=self.admin_a,
                opening_float=Decimal("5000.00"),
                status=CashRegisterSession.Status.OPEN,
            )
            order = Order.objects.create(
                branch=self.branch_a,
                order_type=Order.OrderType.DINE_IN,
                table=table,
                customer=customer,
                customer_name=customer.full_name,
                customer_phone=customer.phone,
            )
            OrderItem.objects.create(
                order=order,
                menu_item=self.dish_a,
                item_name=self.dish_a.name,
                quantity=2,
                unit_price=Decimal("500.00"),
            )
            order.recalculate_totals(tenant=self.tenant_a)

        res = self.http.post(
            f"/api/v1/orders/{order.id}/checkout/",
            data={
                "payment_method": "FONEPAY",
                "customer_pan": "609911223",
            },
            content_type="application/json",
            HTTP_X_TENANT_SLUG="hearth-test",
            HTTP_AUTHORIZATION=f"Bearer {self.token_a}",
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["invoice_number"].startswith("INV-2082-"))
        self.assertEqual(body["order"]["status"], "COMPLETED")
        self.assertEqual(body["order"]["payment_status"], "PAID")

        with schema_context("hearth_test"):
            table.refresh_from_db()
            register.refresh_from_db()
            customer.refresh_from_db()
            self.assertEqual(table.status, DiningTable.Status.AVAILABLE)
            self.assertEqual(register.digital_wallet_sales, Decimal("1243.00"))
            self.assertEqual(customer.loyalty_points, 62)
            self.assertTrue(
                TaxInvoice.objects.filter(
                    order=order, customer_pan="609911223"
                ).exists()
            )
