from django.db import models
from django.utils.text import slugify


class Branch(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=40, blank=True, default="MAIN-01")
    slug = models.SlugField(max_length=100, blank=True)
    is_main_branch = models.BooleanField(default=False)
    address = models.CharField(max_length=300, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="Kathmandu")
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    manager_name = models.CharField(max_length=150, blank=True, default="")
    opening_time = models.TimeField(default="09:00")
    closing_time = models.TimeField(default="22:00")
    operating_hours_json = models.JSONField(default=dict, blank=True)
    holidays_json = models.JSONField(default=list, blank=True)
    pan_vat_number = models.CharField(max_length=60, blank=True, default="")
    tax_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=13.00)
    service_charge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    receipt_header = models.CharField(max_length=300, blank=True, default="")
    receipt_footer = models.CharField(
        max_length=300,
        blank=True,
        default="Thank you for dining with us! Visit again.",
    )
    is_active = models.BooleanField(default=True)
    accepting_online_orders = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_main_branch", "id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "branch"
        if not self.code:
            self.code = (self.slug[:8].upper() or "BR") + "-01"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.code})"
