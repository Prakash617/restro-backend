from django.db import models
from django.utils import timezone
from django_tenants.models import DomainMixin, TenantMixin


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField(blank=True, default="")
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=49.00)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=490.00)
    price_monthly_npr = models.DecimalField(max_digits=12, decimal_places=2, default=4999.00)
    price_yearly_npr = models.DecimalField(max_digits=12, decimal_places=2, default=49990.00)
    trial_days = models.IntegerField(default=14)
    max_branches = models.IntegerField(default=1)
    max_staff_users = models.IntegerField(default=10)
    max_tables = models.IntegerField(default=20)
    max_menu_items = models.IntegerField(default=100)
    max_monthly_orders = models.IntegerField(default=2000)
    enable_pos = models.BooleanField(default=True)
    enable_kds = models.BooleanField(default=True)
    enable_inventory = models.BooleanField(default=True)
    enable_online_ordering = models.BooleanField(default=True)
    enable_table_reservations = models.BooleanField(default=True)
    enable_loyalty_crm = models.BooleanField(default=True)
    enable_multi_branch = models.BooleanField(default=False)
    enable_advanced_analytics = models.BooleanField(default=False)
    enable_custom_domain = models.BooleanField(default=False)
    features_json = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["price_monthly", "id"]

    @property
    def code(self):
        return self.slug.upper()

    def __str__(self):
        return f"{self.name} (${self.price_monthly}/mo)"


class Client(TenantMixin):
    class SubscriptionStatus(models.TextChoices):
        TRIAL = "TRIAL", "Free Trial"
        ACTIVE = "ACTIVE", "Active"
        PAST_DUE = "PAST_DUE", "Past Due"
        SUSPENDED = "SUSPENDED", "Suspended"

    class TaxSystem(models.TextChoices):
        VAT_13_NP = "VAT_13_NP", "Nepal 13% VAT"
        GST = "GST", "GST"
        SALES_TAX = "SALES_TAX", "Sales Tax"
        NONE = "NONE", "No Tax"

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=100, unique=True)
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenants",
    )
    subscription_status = models.CharField(
        max_length=30,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    owner_name = models.CharField(max_length=150, blank=True, default="")
    owner_email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="Kathmandu")
    country = models.CharField(max_length=100, blank=True, default="Nepal")
    cuisine_type = models.CharField(max_length=120, blank=True, default="Multi-Cuisine")
    currency = models.CharField(max_length=10, default="NPR")
    pan_vat_number = models.CharField(max_length=60, blank=True, default="")
    tax_system = models.CharField(
        max_length=30,
        choices=TaxSystem.choices,
        default=TaxSystem.VAT_13_NP,
    )
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=13.00)
    is_tax_inclusive = models.BooleanField(default=False)
    service_charge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    fiscal_year = models.CharField(max_length=20, default="2082/83")
    logo_url = models.CharField(max_length=500, blank=True, default="")
    created_on = models.DateTimeField(auto_now_add=True)

    auto_create_schema = True

    class Meta:
        ordering = ["id"]

    @property
    def subscription_plan(self):
        return self.plan

    def __str__(self):
        return f"{self.name} ({self.slug})"


class Domain(DomainMixin):
    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.domain


class SubscriptionInvoice(models.Model):
    class BillingCycle(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        YEARLY = "YEARLY", "Yearly"

    class PaymentGateway(models.TextChoices):
        ESEWA = "ESEWA", "eSewa"
        KHALTI = "KHALTI", "Khalti"
        FONEPAY = "FONEPAY", "Fonepay"
        STRIPE = "STRIPE", "Stripe"
        MANUAL = "MANUAL", "Manual / Bank Transfer"

    class Status(models.TextChoices):
        PAID = "PAID", "Paid"
        PENDING = "PENDING", "Pending"
        FAILED = "FAILED", "Failed"

    tenant = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="subscription_invoices",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=60, unique=True)
    billing_cycle = models.CharField(
        max_length=20,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default="USD")
    payment_gateway = models.CharField(
        max_length=30,
        choices=PaymentGateway.choices,
        default=PaymentGateway.STRIPE,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PAID,
    )
    period_start = models.DateField(default=timezone.now)
    period_end = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.invoice_number} - {self.tenant.name} ({self.status})"
