import secrets
from decimal import Decimal
from django.db import models
from django.utils import timezone


class Order(models.Model):
    class OrderType(models.TextChoices):
        DINE_IN = "DINE_IN", "Dine-In"
        TAKEAWAY = "TAKEAWAY", "Takeaway"
        DELIVERY = "DELIVERY", "Delivery"
        QR_ORDER = "QR_ORDER", "QR Table Order"

    class Channel(models.TextChoices):
        POS = "POS", "POS Terminal"
        WAITER = "WAITER", "Waiter Handheld"
        QR_MENU = "QR_MENU", "Table QR Scan"
        WEBSITE = "WEBSITE", "Online Website"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        IN_KITCHEN = "IN_KITCHEN", "In Kitchen (KDS)"
        READY = "READY", "Ready to Serve"
        SERVED = "SERVED", "Served"
        COMPLETED = "COMPLETED", "Completed & Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentStatus(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PARTIAL = "PARTIAL", "Partially Paid"
        PAID = "PAID", "Paid"
        REFUNDED = "REFUNDED", "Refunded"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card / POS Terminal"
        ESEWA = "ESEWA", "eSewa Wallet"
        KHALTI = "KHALTI", "Khalti Wallet"
        FONEPAY = "FONEPAY", "Fonepay Dynamic QR"
        QR_WALLET = "QR_WALLET", "QR / Digital Wallet"
        SPLIT = "SPLIT", "Split Payment"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    order_number = models.CharField(max_length=60, unique=True, blank=True)
    order_type = models.CharField(
        max_length=20,
        choices=OrderType.choices,
        default=OrderType.DINE_IN,
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.POS,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_KITCHEN,
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    table = models.ForeignKey(
        "tables.DiningTable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    waiter = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waiter_orders",
    )
    cashier = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cashier_orders",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    customer_name = models.CharField(
        max_length=150, blank=True, default="Walk-in Guest"
    )
    customer_phone = models.CharField(max_length=50, blank=True, default="")
    customer_address = models.CharField(max_length=300, blank=True, default="")
    customer_pan = models.CharField(max_length=60, blank=True, default="")
    guest_count = models.IntegerField(default=2)
    coupon_code = models.CharField(max_length=40, blank=True, default="")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    service_charge = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    loyalty_points_earned = models.IntegerField(default=0)
    loyalty_points_redeemed = models.IntegerField(default=0)
    refund_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    refund_reason = models.CharField(max_length=250, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{timezone.now().strftime('%m%d')}-{secrets.token_hex(2).upper()}"
        super().save(*args, **kwargs)

    def recalculate_totals(self, tenant=None):
        items_qs = self.items.all()
        sub = Decimal("0.00")
        for it in items_qs:
            sub += Decimal(str(it.unit_price)) * Decimal(str(it.quantity))
        self.subtotal = sub.quantize(Decimal("0.01"))

        discount = Decimal(str(self.discount_amount or "0.00")).quantize(
            Decimal("0.01")
        )
        self.discount_amount = discount
        discounted_subtotal = max(Decimal("0.00"), self.subtotal - discount)

        sc_rate = Decimal("10.00")
        tax_rate = Decimal("13.00")
        if self.branch:
            sc_rate = Decimal(str(self.branch.service_charge_percent))
            tax_rate = Decimal(str(self.branch.tax_rate_percent))
        elif tenant and getattr(tenant, "schema_name", "public") != "public":
            sc_rate = Decimal(str(tenant.service_charge_percent))
            tax_rate = Decimal(str(tenant.tax_rate_percent))

        self.service_charge = (
            discounted_subtotal * (sc_rate / Decimal("100.00"))
        ).quantize(Decimal("0.01"))
        taxable_amount = discounted_subtotal + self.service_charge
        self.tax_amount = (
            taxable_amount * (tax_rate / Decimal("100.00"))
        ).quantize(Decimal("0.01"))
        self.total_amount = (taxable_amount + self.tax_amount).quantize(
            Decimal("0.01")
        )
        self.loyalty_points_earned = int(self.total_amount // Decimal("100"))
        self.save(
            update_fields=[
                "subtotal",
                "discount_amount",
                "service_charge",
                "tax_amount",
                "total_amount",
                "loyalty_points_earned",
                "updated_at",
            ]
        )

    def __str__(self):
        return f"{self.order_number} ({self.status}) - {self.total_amount}"


class OrderItem(models.Model):
    class Course(models.TextChoices):
        STARTER = "STARTER", "Starter / Appetizer"
        MAIN = "MAIN", "Main Course"
        DESSERT = "DESSERT", "Dessert"
        DRINKS = "DRINKS", "Beverages & Drinks"

    class KotStatus(models.TextChoices):
        QUEUED = "QUEUED", "Queued"
        PREPARING = "PREPARING", "Preparing"
        READY = "READY", "Ready"
        SERVED = "SERVED", "Served"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    menu_item = models.ForeignKey(
        "menu.MenuItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    item_name = models.CharField(max_length=160)
    variant_name = models.CharField(max_length=80, blank=True, default="")
    kitchen_station = models.CharField(max_length=30, default="HOT_KITCHEN")
    course = models.CharField(
        max_length=20,
        choices=Course.choices,
        default=Course.MAIN,
    )
    quantity = models.IntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    modifiers_json = models.JSONField(default=list, blank=True)
    special_instructions = models.CharField(max_length=250, blank=True, default="")
    kot_batch = models.IntegerField(default=1)
    kot_status = models.CharField(
        max_length=20,
        choices=KotStatus.choices,
        default=KotStatus.QUEUED,
    )
    is_stock_deducted = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["kot_batch", "id"]

    @property
    def line_total(self):
        return round(
            Decimal(str(self.unit_price)) * Decimal(str(self.quantity)), 2
        )

    def __str__(self):
        return f"{self.quantity}x {self.item_name} ({self.kot_status})"


class PaymentTransaction(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        CARD = "CARD", "Card"
        ESEWA = "ESEWA", "eSewa"
        KHALTI = "KHALTI", "Khalti"
        FONEPAY = "FONEPAY", "Fonepay QR"
        QR_WALLET = "QR_WALLET", "Digital QR Wallet"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    method = models.CharField(
        max_length=25,
        choices=Method.choices,
        default=Method.CASH,
    )
    reference = models.CharField(max_length=100, blank=True, default="")
    paid_by_label = models.CharField(
        max_length=100, blank=True, default="Primary Guest"
    )
    gateway_status = models.CharField(max_length=30, default="SUCCESS")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.order.order_number} - {self.method}: {self.amount}"


def deduct_stock_for_order_item(order_item):
    """
    Deducts RecipeIngredient quantities from InventoryItem.current_stock
    when an OrderItem reaches READY/SERVED or Order is COMPLETED.
    Idempotent via `order_item.is_stock_deducted`.
    """
    if order_item.is_stock_deducted or not order_item.menu_item_id:
        return

    from apps.inventory.models import RecipeIngredient, StockMovement
    from apps.notifications.models import Notification

    recipes = RecipeIngredient.objects.select_related("inventory_item").filter(
        menu_item_id=order_item.menu_item_id
    )
    for recipe in recipes:
        inv_item = recipe.inventory_item
        consumed_qty = Decimal(str(recipe.quantity_required)) * Decimal(
            str(order_item.quantity)
        )
        inv_item.current_stock = max(
            Decimal("0.000"), inv_item.current_stock - consumed_qty
        )
        inv_item.save(update_fields=["current_stock"])

        StockMovement.objects.create(
            item=inv_item,
            branch=order_item.order.branch or inv_item.branch,
            movement_type=StockMovement.MovementType.CONSUMPTION,
            quantity=-consumed_qty,
            reason=f"Auto-deducted for {order_item.quantity}x {order_item.item_name}",
            reference=order_item.order.order_number,
        )

        if inv_item.is_low_stock:
            Notification.objects.create(
                branch=order_item.order.branch or inv_item.branch,
                category=Notification.Category.LOW_STOCK,
                severity=Notification.Severity.WARNING,
                title=f"Low Stock Alert: {inv_item.name}",
                message=(
                    f"{inv_item.name} is down to {inv_item.current_stock} {inv_item.unit} "
                    f"(reorder level: {inv_item.reorder_level} {inv_item.unit})."
                ),
                action_url="/dashboard/inventory",
            )

    order_item.is_stock_deducted = True
    order_item.save(update_fields=["is_stock_deducted"])


def deduct_stock_for_order(order):
    for item in order.items.filter(is_stock_deducted=False):
        deduct_stock_for_order_item(item)
