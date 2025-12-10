from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from datetime import timedelta
from decimal import Decimal

# Create your models here.

class AttendanceStatus(models.Model):
    """
    Master table for attendance statuses.
    Replaces TextChoices so statuses are stored dynamically in DB.
    """
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        null=True,
        related_name="owner_attendance_status",
        limit_choices_to={"user_type": "VSRE_OWNER"}
    )

    code = models.CharField(max_length=20, unique=True)   # e.g., PRESENT
    label = models.CharField(max_length=50)               # e.g., Present
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Attendance Status"
        verbose_name_plural = "Attendance Statuses"
        ordering = ["label"]
    
    

    def __str__(self):
        return f"{self.label} ({self.code})"

class Attendance(models.Model):
    """
    Attendance model using the AttendanceStatus table.
    Tracks individual attendance records and calculates totals across time periods.
    """

    # Core fields
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="attendance",
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER", "VSRE_STAFF"]}
    )

    date = models.DateField(default=timezone.now)
    duration = models.DurationField(null=True, blank=True, help_text="Duration of attendance for this day")

    status = models.ForeignKey(
        AttendanceStatus,
        on_delete=models.PROTECT,
        related_name="attendance_status",
        help_text="Present / Absent / Half Day / Paid Leave / Unpaid Leave"
    )

    reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ["-date"]
        verbose_name = "Attendance"
        verbose_name_plural = "Attendance"
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["user", "-date"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.date} ({self.status.label})"

class TotalAttendance(models.Model):
    """
    Stores aggregated attendance hours for a user.
    These records will be updated from Attendance model via signals.
    """

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="total_attendance",
        limit_choices_to={
            "user_type__in": ["VSRE_MANAGER", "LINE_MANAGER", "VSRE_STAFF"]
        }
    )

    # Aggregated period totals
    total_hours_day = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Total hours for this day"
    )

    total_hours_week = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        help_text="Total hours for the week (Mon-Sun)"
    )

    total_hours_fortnight = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Total hours for the fortnight (14 days)"
    )

    total_hours_month = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=0,
        help_text="Total hours for the calendar month"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Total Attendance"
        verbose_name_plural = "Total Attendance Records"
        indexes = [
            models.Index(fields=["user", "updated_at"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()}"
