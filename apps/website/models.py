from django.db import models
from django.utils import timezone


class RestaurantWebsiteSettings(models.Model):
    class ThemeId(models.TextChoices):
        BISTRO_ELEGANCE = "bistro-elegance", "Bistro Elegance"
        URBAN_STREET = "urban-street", "Urban Street & Izakaya"
        FINE_DINING_GOLD = "fine-dining-gold", "Fine Dining Gold"
        CAFE_MINIMAL = "cafe-minimal", "Café Minimal & Roastery"

    class ColorPalette(models.TextChoices):
        EMBER_TERRACOTTA = "ember-terracotta", "Ember Terracotta"
        OLIVE_HARVEST = "olive-harvest", "Olive Harvest"
        MIDNIGHT_GOLD = "midnight-gold", "Midnight Gold"
        BERRY_BISTRO = "berry-bistro", "Berry Bistro"
        OCEAN_CATCH = "ocean-catch", "Ocean Catch"
        ESPRESSO_WARM = "espresso-warm", "Espresso Warm"

    theme_id = models.CharField(
        max_length=40,
        choices=ThemeId.choices,
        default=ThemeId.BISTRO_ELEGANCE,
    )
    color_palette = models.CharField(
        max_length=40,
        choices=ColorPalette.choices,
        default=ColorPalette.EMBER_TERRACOTTA,
    )
    custom_primary_hex = models.CharField(max_length=20, blank=True, default="")
    tagline = models.CharField(
        max_length=220,
        blank=True,
        default="Crafted with Passion, Served with Warm Hospitality",
    )
    hero_title = models.CharField(
        max_length=200,
        blank=True,
        default="Artisan Dining & Wood-Fired Gastronomy",
    )
    hero_subtitle = models.TextField(
        blank=True,
        default="Experience locally sourced seasonal ingredients, signature chef specials, and effortless online ordering or table booking.",
    )
    hero_badge_text = models.CharField(
        max_length=100, blank=True, default="Reserve a Table or Order Online"
    )
    hero_cta_text = models.CharField(
        max_length=80, blank=True, default="Explore Digital Menu"
    )
    hero_image_url = models.CharField(max_length=500, blank=True, default="")
    about_title = models.CharField(
        max_length=180, blank=True, default="Our Culinary Philosophy"
    )
    about_story = models.TextField(
        blank=True,
        default="Founded on a dedication to authentic flavors and warm table hospitality, our kitchen prepares every dish fresh to order.",
    )
    chef_name = models.CharField(
        max_length=120, blank=True, default="Chef Aarav Thapa"
    )
    chef_title = models.CharField(
        max_length=120, blank=True, default="Executive Culinary Director"
    )
    chef_quote = models.TextField(
        blank=True,
        default="Great food honors its ingredients, the fire it's cooked over, and the people gathered around the table.",
    )
    chef_image_url = models.CharField(max_length=500, blank=True, default="")
    opening_hours_text = models.CharField(
        max_length=200,
        blank=True,
        default="Mon – Sun: 10:00 AM – 10:30 PM",
    )
    address = models.CharField(
        max_length=250, blank=True, default="Thamel Marg, Kathmandu, Nepal"
    )
    phone = models.CharField(
        max_length=50, blank=True, default="+977-1-4429800"
    )
    email = models.EmailField(blank=True, default="hello@restaurant.com")
    instagram_url = models.CharField(max_length=300, blank=True, default="")
    facebook_url = models.CharField(max_length=300, blank=True, default="")
    tiktok_url = models.CharField(max_length=300, blank=True, default="")
    delivery_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=100.00
    )
    min_delivery_order = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00
    )
    estimated_delivery_mins = models.IntegerField(default=35)
    accepting_online_orders = models.BooleanField(default=True)
    accepting_reservations = models.BooleanField(default=True)
    qr_ordering_enabled = models.BooleanField(default=True)
    gallery_json = models.JSONField(default=list, blank=True)
    highlights_json = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"Website Settings ({self.theme_id} / {self.color_palette})"


class Testimonial(models.Model):
    guest_name = models.CharField(max_length=150)
    guest_role = models.CharField(
        max_length=120, blank=True, default="Verified Diner"
    )
    rating = models.IntegerField(default=5)
    comment = models.TextField()
    dish_ordered = models.CharField(max_length=150, blank=True, default="")
    visit_date = models.DateField(default=timezone.now)
    avatar_url = models.CharField(max_length=500, blank=True, default="")
    is_featured = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_featured", "-rating", "-id"]

    def __str__(self):
        return f"{self.guest_name} ({self.rating}/5)"
