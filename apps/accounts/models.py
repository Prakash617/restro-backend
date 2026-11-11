from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_password("Admin@12345")
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.SUPERADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "SuperAdmin"
        RESTAURANT_ADMIN = "RESTAURANT_ADMIN", "Restaurant Admin"
        MANAGER = "MANAGER", "Floor / Operations Manager"
        CASHIER = "CASHIER", "POS Cashier"
        WAITER = "WAITER", "Waiter / Server"
        CHEF = "CHEF", "Executive / Line Chef"
        DELIVERY = "DELIVERY", "Delivery Rider"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    role = models.CharField(
        max_length=30,
        choices=Role.choices,
        default=Role.WAITER,
    )
    phone = models.CharField(max_length=50, blank=True, default="")
    department = models.CharField(max_length=120, blank=True, default="")
    specialization = models.CharField(max_length=200, blank=True, default="")
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    pos_pin = models.CharField(max_length=10, default="1234")
    permissions_json = models.JSONField(default=list, blank=True)
    avatar_url = models.CharField(max_length=500, blank=True, default="")
    is_public_staff = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"


class StaffShift(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        CHECKED_IN = "CHECKED_IN", "Checked In"
        COMPLETED = "COMPLETED", "Completed"
        ABSENT = "ABSENT", "Absent"

    staff = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="shifts",
    )
    role_on_shift = models.CharField(max_length=50, blank=True, default="WAITER")
    shift_date = models.DateField(default=timezone.now)
    start_time = models.TimeField()
    end_time = models.TimeField()
    station = models.CharField(max_length=80, blank=True, default="FLOOR_A")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    clock_in_at = models.DateTimeField(null=True, blank=True)
    clock_out_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-shift_date", "start_time", "id"]

    def __str__(self):
        return f"{self.staff.full_name} - {self.shift_date} ({self.station})"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        ORDER_CREATED = "ORDER_CREATED", "Order Created"
        ORDER_VOID = "ORDER_VOID", "Order Voided"
        DISCOUNT_APPLIED = "DISCOUNT_APPLIED", "Discount Applied"
        REFUND_ISSUED = "REFUND_ISSUED", "Refund Issued"
        REGISTER_OPENED = "REGISTER_OPENED", "Cash Register Opened"
        REGISTER_CLOSED = "REGISTER_CLOSED", "Cash Register Closed"
        STOCK_WASTAGE = "STOCK_WASTAGE", "Stock Wastage / Adjustment"
        PRICE_UPDATED = "PRICE_UPDATED", "Menu Price Updated"
        TABLE_MERGED = "TABLE_MERGED", "Tables Merged"
        TABLE_TRANSFERRED = "TABLE_TRANSFERRED", "Table Transferred"
        SETTINGS_UPDATED = "SETTINGS_UPDATED", "Settings Updated"

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor_name = models.CharField(max_length=150, blank=True, default="System")
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(
        max_length=40,
        choices=Action.choices,
        default=Action.ORDER_CREATED,
    )
    target_model = models.CharField(max_length=100, blank=True, default="")
    target_id = models.CharField(max_length=60, blank=True, default="")
    description = models.TextField(blank=True, default="")
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"[{self.action}] {self.actor_name}: {self.description[:60]}"
