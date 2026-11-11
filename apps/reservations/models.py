import secrets
from django.db import models
from django.utils import timezone


class TableReservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Confirmation"
        CONFIRMED = "CONFIRMED", "Confirmed"
        WAITLIST = "WAITLIST", "Waitlist"
        SEATED = "SEATED", "Seated at Table"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        NO_SHOW = "NO_SHOW", "No Show"

    class Occasion(models.TextChoices):
        NONE = "NONE", "Regular Dining"
        BIRTHDAY = "BIRTHDAY", "Birthday Celebration"
        ANNIVERSARY = "ANNIVERSARY", "Anniversary"
        BUSINESS = "BUSINESS", "Business Dinner"
        VIP = "VIP", "VIP / Chef's Table"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    reservation_code = models.CharField(max_length=40, unique=True, blank=True)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    guest_name = models.CharField(max_length=150)
    guest_phone = models.CharField(max_length=50)
    guest_email = models.EmailField(blank=True, default="")
    party_size = models.IntegerField(default=2)
    reservation_date = models.DateField(default=timezone.now)
    reservation_time = models.TimeField(default="19:00")
    duration_minutes = models.IntegerField(default=90)
    table = models.ForeignKey(
        "tables.DiningTable",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )
    occasion = models.CharField(
        max_length=25,
        choices=Occasion.choices,
        default=Occasion.NONE,
    )
    special_requests = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["reservation_date", "reservation_time", "-id"]

    def save(self, *args, **kwargs):
        if not self.reservation_code:
            self.reservation_code = f"RES-{secrets.token_hex(3).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reservation_code} - {self.guest_name} ({self.party_size} guests)"
