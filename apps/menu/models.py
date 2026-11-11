from django.db import models
from django.utils.text import slugify


class MenuCategory(models.Model):
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, blank=True)
    description = models.TextField(blank=True, default="")
    icon = models.CharField(max_length=80, blank=True, default="utensils")
    display_order = models.IntegerField(default=0)
    available_from = models.TimeField(null=True, blank=True)
    available_until = models.TimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "category"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    class KitchenStation(models.TextChoices):
        HOT_KITCHEN = "HOT_KITCHEN", "Hot Kitchen"
        GRILL = "GRILL", "Wood-Fired Grill & Tandoor"
        BAR = "BAR", "Bar & Beverage"
        BAKERY = "BAKERY", "Bakery & Pastry"
        COLD_PANTRY = "COLD_PANTRY", "Cold Pantry & Salads"

    class SpiceLevel(models.TextChoices):
        NONE = "NONE", "None"
        MILD = "MILD", "Mild"
        MEDIUM = "MEDIUM", "Medium"
        HOT = "HOT", "Hot"
        EXTRA_HOT = "EXTRA_HOT", "Extra Hot"

    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.CASCADE,
        related_name="items",
    )
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, blank=True)
    sku = models.CharField(max_length=60, blank=True, default="")
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    prep_time_minutes = models.IntegerField(default=12)
    kitchen_station = models.CharField(
        max_length=30,
        choices=KitchenStation.choices,
        default=KitchenStation.HOT_KITCHEN,
    )
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_gluten_free = models.BooleanField(default=False)
    spice_level = models.CharField(
        max_length=20,
        choices=SpiceLevel.choices,
        default=SpiceLevel.NONE,
    )
    allergens_json = models.JSONField(default=list, blank=True)
    calories = models.IntegerField(null=True, blank=True, default=350)
    image_url = models.CharField(max_length=500, blank=True, default="")
    is_available = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    variants_json = models.JSONField(default=list, blank=True)
    modifiers_json = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category__display_order", "-is_featured", "id"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name) or "dish"
        if not self.sku:
            self.sku = (self.slug[:10].upper().replace("-", "") or "ITEM") + "-01"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.price})"
