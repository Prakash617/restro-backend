from django.db import models
from django.utils import timezone


class Customer(models.Model):
    class Tier(models.TextChoices):
        BRONZE = "BRONZE", "Bronze"
        SILVER = "SILVER", "Silver"
        GOLD = "GOLD", "Gold"
        PLATINUM = "PLATINUM", "Platinum VIP"

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=50)
    email = models.EmailField(blank=True, default="")
    tier = models.CharField(
        max_length=20,
        choices=Tier.choices,
        default=Tier.BRONZE,
    )
    loyalty_points = models.IntegerField(default=0)
    lifetime_points = models.IntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    visits_count = models.IntegerField(default=1)
    dietary_notes = models.TextField(blank=True, default="")
    birthday = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-total_spent", "-id"]

    def recalculate_tier(self):
        if self.lifetime_points >= 2500:
            self.tier = self.Tier.PLATINUM
        elif self.lifetime_points >= 1000:
            self.tier = self.Tier.GOLD
        elif self.lifetime_points >= 350:
            self.tier = self.Tier.SILVER
        else:
            self.tier = self.Tier.BRONZE

    def __str__(self):
        return f"{self.full_name} ({self.phone}) - {self.tier}"


class LoyaltyTransaction(models.Model):
    class TransactionType(models.TextChoices):
        EARNED = "EARNED", "Earned on Order"
        REDEEMED = "REDEEMED", "Redeemed on Bill"
        BONUS = "BONUS", "Promo / Tier Bonus"
        ADJUSTMENT = "ADJUSTMENT", "Manual Adjustment"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="loyalty_transactions",
    )
    order_number = models.CharField(max_length=60, blank=True, default="")
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.EARNED,
    )
    points = models.IntegerField(default=0)
    description = models.CharField(max_length=250, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.customer.full_name}: {self.points} pts ({self.transaction_type})"


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Percentage (%)"
        FIXED = "FIXED", "Fixed Amount"

    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=150)
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE,
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00
    )
    valid_from = models.DateField(default=timezone.now)
    valid_until = models.DateField(null=True, blank=True)
    usage_limit = models.IntegerField(default=500)
    used_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_active", "code"]

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.title}"


class CustomerFeedback(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="feedbacks",
    )
    guest_name = models.CharField(max_length=150)
    order_number = models.CharField(max_length=60, blank=True, default="")
    food_rating = models.IntegerField(default=5)
    service_rating = models.IntegerField(default=5)
    ambience_rating = models.IntegerField(default=5)
    overall_rating = models.IntegerField(default=5)
    comment = models.TextField(blank=True, default="")
    is_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.guest_name} ({self.overall_rating}/5)"
