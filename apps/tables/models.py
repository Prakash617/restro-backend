import secrets
from django.db import models


class DiningZone(models.Model):
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="zones",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=40, blank=True, default="FLOOR-A")
    floor_number = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["floor_number", "id"]

    def __str__(self):
        return f"{self.name} (Floor {self.floor_number})"


class DiningTable(models.Model):
    class Shape(models.TextChoices):
        SQUARE = "SQUARE", "Square"
        ROUND = "ROUND", "Round"
        BOOTH = "BOOTH", "Booth"
        RECTANGLE = "RECTANGLE", "Rectangle"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        OCCUPIED = "OCCUPIED", "Occupied"
        RESERVED = "RESERVED", "Reserved"
        BILL_PRINTED = "BILL_PRINTED", "Bill Printed"
        DIRTY = "DIRTY", "Needs Cleaning"

    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tables",
    )
    zone = models.ForeignKey(
        DiningZone,
        on_delete=models.CASCADE,
        related_name="tables",
    )
    table_number = models.CharField(max_length=40)
    capacity = models.IntegerField(default=4)
    shape = models.CharField(
        max_length=20,
        choices=Shape.choices,
        default=Shape.SQUARE,
    )
    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="merged_tables",
    )
    current_guest_count = models.IntegerField(default=0)
    qr_code_token = models.CharField(max_length=80, blank=True, default="")
    pos_x = models.IntegerField(default=0)
    pos_y = models.IntegerField(default=0)
    notes = models.CharField(max_length=250, blank=True, default="")

    class Meta:
        ordering = ["zone__floor_number", "table_number", "id"]

    def save(self, *args, **kwargs):
        if not self.qr_code_token:
            self.qr_code_token = f"qr-{self.table_number.lower()}-{secrets.token_hex(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Table {self.table_number} ({self.status})"
