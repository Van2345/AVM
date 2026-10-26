from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class AssistanceUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", "ADMIN")
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        VOLUNTEER = "VOLUNTEER", "Volunteer"
        REQUESTER = "REQUESTER", "Requester"

    full_name = models.CharField(max_length=100)
    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.REQUESTER
    )
    created_at = models.DateTimeField(auto_now_add=True)
    REQUIRED_FIELDS = ["full_name"]
    objects = AssistanceUserManager()


class Volunteer(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        BUSY = "BUSY", "Busy"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    volunteer_code = models.CharField(max_length=10, unique=True, null=True, blank=True)
    user = models.OneToOneField(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="volunteer"
    )
    full_name = models.CharField(max_length=100)
    contact = models.CharField(max_length=20)
    skill = models.CharField(max_length=80)
    availability = models.CharField(max_length=100)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.AVAILABLE
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_accuracy = models.DecimalField(
        max_digits=8, decimal_places=1, null=True, blank=True
    )
    location_updated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.volunteer_code or self.full_name


class AssistanceRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        ASSIGNED = "ASSIGNED", "Assigned"
        ONGOING = "ONGOING", "Ongoing"
        DONE = "DONE", "Done"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    class Urgency(models.TextChoices):
        LOW = "Low", "Low"
        MEDIUM = "Medium", "Medium"
        HIGH = "High", "High"
        EMERGENCY = "Emergency", "Emergency"

    request_code = models.CharField(max_length=12, unique=True, null=True, blank=True)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assistance_requests",
    )
    requester_name = models.CharField(max_length=100)
    contact = models.CharField(max_length=20)
    assistance_type = models.CharField(max_length=40)
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    description = models.TextField()
    urgency = models.CharField(max_length=10, choices=Urgency.choices, default=Urgency.LOW)
    needed_at = models.DateTimeField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.request_code or f"Request {self.pk}"


class Assignment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    request = models.ForeignKey(
        AssistanceRequest, on_delete=models.CASCADE, related_name="assignments"
    )
    volunteer = models.ForeignKey(
        Volunteer, on_delete=models.CASCADE, related_name="assignments"
    )
    assigned_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="assignments"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE
    )


class ActivityLog(models.Model):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="activity_logs"
    )
    request = models.ForeignKey(
        AssistanceRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=40)
    details = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.details
