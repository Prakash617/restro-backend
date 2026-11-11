from decimal import Decimal
from django.db import models
from django.utils import timezone


class CashRegisterSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="register_sessions",
    )
    opened_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opened_registers",
    )
    closed_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="closed_registers",
    )
    register_name = models.CharField(
        max_length=120, default="Main POS Register #1"
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.OPEN,
    )
    opening_float = models.DecimalField(
        max_digits=12, decimal_places=2, default=5000.00
    )
    cash_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    card_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    digital_wallet_sales = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    cash_in = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cash_out = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    expected_closing_cash = models.DecimalField(
        max_digits=12, decimal_places=2, default=5000.00
    )
    actual_closing_cash = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    variance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, default="")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at", "-id"]

    def recalculate_expected(self):
        self.expected_closing_cash = (
            Decimal(str(self.opening_float or "0"))
            + Decimal(str(self.cash_sales or "0"))
            + Decimal(str(self.cash_in or "0"))
            - Decimal(str(self.cash_out or "0"))
        ).quantize(Decimal("0.01"))
        if self.status == self.Status.CLOSED:
            self.variance = (
                Decimal(str(self.actual_closing_cash or "0"))
                - self.expected_closing_cash
            ).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        self.recalculate_expected()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.register_name} ({self.status})"


class TaxInvoice(models.Model):
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tax_invoices",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="tax_invoice",
    )
    invoice_number = models.CharField(max_length=60, unique=True)
    fiscal_year = models.CharField(max_length=20, default="2082/83")
    seller_pan = models.CharField(max_length=60, blank=True, default="609812345")
    customer_name = models.CharField(
        max_length=150, blank=True, default="Walk-in Guest"
    )
    customer_pan = models.CharField(max_length=60, blank=True, default="")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    service_charge = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    taxable_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00
    )
    tax_rate_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=13.00
    )
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=30, default="CASH")
    print_count = models.IntegerField(default=1)
    is_void = models.BooleanField(default=False)
    void_reason = models.CharField(max_length=250, blank=True, default="")
    issued_by_name = models.CharField(
        max_length=150, blank=True, default="POS Cashier"
    )
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issued_at", "-id"]

    @classmethod
    def generate_next_invoice_number(cls, fiscal_year="2082/83"):
        fy_prefix = (fiscal_year or "2082").split("/")[0]
        seq = cls.objects.count() + 1
        candidate = f"INV-{fy_prefix}-{seq:04d}"
        while cls.objects.filter(invoice_number=candidate).exists():
            seq += 1
            candidate = f"INV-{fy_prefix}-{seq:04d}"
        return candidate

    def __str__(self):
        return f"{self.invoice_number} ({self.grand_total})"


class Expense(models.Model):
    class Category(models.TextChoices):
        INGREDIENTS = "INGREDIENTS", "Ingredients & Raw Materials"
        UTILITIES = "UTILITIES", "Utilities (Electricity, Gas, Water)"
        RENT = "RENT", "Premises Rent"
        PAYROLL = "PAYROLL", "Staff Payroll & Wages"
        EQUIPMENT = "EQUIPMENT", "Kitchen & POS Equipment"
        MARKETING = "MARKETING", "Marketing & Promotions"
        OTHER = "OTHER", "Other Operating Expenses"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.INGREDIENTS,
    )
    title = models.CharField(max_length=180)
    vendor_name = models.CharField(max_length=150, blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=30, default="CASH")
    reference_number = models.CharField(max_length=80, blank=True, default="")
    expense_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_expenses",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-expense_date", "-id"]

    def __str__(self):
        return f"{self.title} ({self.amount})"
