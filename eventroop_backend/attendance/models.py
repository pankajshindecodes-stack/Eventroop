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
        related_name="attendance_statuses",
        limit_choices_to={"user_type":"VSRE_OWNER"}
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

class AttendanceReport(models.Model):
    """Pre-calculated attendance and salary report stored in database"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attendance_reports')
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Attendance data
    present_days = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    absent_days = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    half_day_count = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_leave_days = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weekly_Offs = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unpaid_leaves = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_payable_days = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_payable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    
    # Salary data
    salary_type = models.CharField(max_length=50, null=True, blank=True)
    final_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    current_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_payable_days = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    remaining_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'start_date', 'end_date')
        indexes = [
            models.Index(fields=['user', 'start_date', 'end_date']),
            models.Index(fields=['user', 'updated_at']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.start_date} to {self.end_date}"

