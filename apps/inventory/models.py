from django.db import models
from django.utils import timezone


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    address = models.CharField(max_length=250, blank=True, default="")
    pan_number = models.CharField(max_length=60, blank=True, default="")
    category = models.CharField(max_length=80, blank=True, default="General Wholesale")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    class Category(models.TextChoices):
        PRODUCE = "PRODUCE", "Fresh Produce"
        MEAT_SEAFOOD = "MEAT_SEAFOOD", "Meat & Seafood"
        DAIRY = "DAIRY", "Dairy & Eggs"
        DRY_GOODS = "DRY_GOODS", "Dry Goods & Spices"
        BEVERAGES = "BEVERAGES", "Beverages & Syrups"
        PACKAGING = "PACKAGING", "Packaging & Disposables"

    class Unit(models.TextChoices):
        KG = "kg", "Kilograms (kg)"
        G = "g", "Grams (g)"
        LTR = "ltr", "Liters (ltr)"
        ML = "ml", "Milliliters (ml)"
        PCS = "pcs", "Pieces (pcs)"
        PACK = "pack", "Packs"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_items",
    )
    sku = models.CharField(max_length=60, blank=True, default="")
    name = models.CharField(max_length=150)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.PRODUCE,
    )
    unit = models.CharField(
        max_length=15,
        choices=Unit.choices,
        default=Unit.KG,
    )
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=5.000)
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    last_restocked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["category", "name", "id"]

    @property
    def is_low_stock(self):
        return self.current_stock <= self.reorder_level

    def save(self, *args, **kwargs):
        if not self.sku:
            prefix = self.name[:6].upper().replace(" ", "") or "INV"
            self.sku = f"{prefix}-01"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"


class RecipeIngredient(models.Model):
    menu_item = models.ForeignKey(
        "menu.MenuItem",
        on_delete=models.CASCADE,
        related_name="recipe_items",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="used_in_recipes",
    )
    quantity_required = models.DecimalField(
        max_digits=10, decimal_places=3, default=0.100
    )
    unit_note = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.menu_item.name} -> {self.quantity_required} {self.inventory_item.unit} {self.inventory_item.name}"


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        RESTOCK = "RESTOCK", "Restock"
        CONSUMPTION = "CONSUMPTION", "Order Recipe Consumption"
        WASTAGE = "WASTAGE", "Kitchen Wastage / Spoilage"
        ADJUSTMENT = "ADJUSTMENT", "Manual Audit Adjustment"
        PO_RECEIPT = "PO_RECEIPT", "Purchase Order Receipt"

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    movement_type = models.CharField(
        max_length=25,
        choices=MovementType.choices,
        default=MovementType.RESTOCK,
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    reason = models.CharField(max_length=250, blank=True, default="")
    reference = models.CharField(max_length=100, blank=True, default="")
    performed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.movement_type}: {self.quantity} {self.item.name}"


class PurchaseOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ORDERED = "ORDERED", "Ordered"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially Received"
        RECEIVED = "RECEIVED", "Received"
        CANCELLED = "CANCELLED", "Cancelled"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    po_number = models.CharField(max_length=60, unique=True)
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name="purchase_orders",
    )
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.ORDERED,
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if not self.po_number:
            count = PurchaseOrder.objects.count() + 1
            self.po_number = f"PO-{timezone.now().strftime('%Y%m')}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name} ({self.status})"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    inventory_item = models.ForeignKey(
        InventoryItem,
        on_delete=models.CASCADE,
        related_name="po_items",
    )
    quantity_ordered = models.DecimalField(
        max_digits=12, decimal_places=3, default=1.000
    )
    quantity_received = models.DecimalField(
        max_digits=12, decimal_places=3, default=0.000
    )
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.purchase_order.po_number}: {self.quantity_ordered} {self.inventory_item.name}"
