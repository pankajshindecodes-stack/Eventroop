from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from datetime import timedelta
from decimal import Decimal
from django.core.validators import MinValueValidator

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
    """
    Pre-calculated attendance report stored in database.
    Auto-updated via signals when attendance records change.
    """
    
    PERIOD_CHOICES = [
        ('HOURLY', 'Hourly'),
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('FORTNIGHTLY', 'Fortnightly'),
        ('MONTHLY', 'Monthly'),
    ]
    
    # Core relationships
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='attendance_reports'
    )
    
    # Period information
    start_date = models.DateField()
    end_date = models.DateField()
    period_type = models.CharField(
        max_length=20,
        choices=PERIOD_CHOICES,
        default='MONTHLY'
    )
    
    # Attendance metrics
    present_days = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    absent_days = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    half_day_count = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    paid_leave_days = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    weekly_Offs = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    unpaid_leaves = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_payable_days = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    total_payable_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('user', 'start_date', 'end_date', 'period_type')
        indexes = [
            models.Index(fields=['user', 'start_date', 'end_date']),
            models.Index(fields=['user', 'period_type']),
            models.Index(fields=['user', 'updated_at']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        ordering = ['-start_date']
        verbose_name = 'Attendance Report'
        verbose_name_plural = 'Attendance Reports'
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.start_date} to {self.end_date}"
    
    @property
    def total_days_worked(self):
        """Calculate total days worked (present + half-day)."""
        return self.present_days + (self.half_day_count * Decimal('0.5'))
    
    @property
    def total_days_absent(self):
        """Calculate total days absent (absent + unpaid leave)."""
        return self.absent_days + self.unpaid_leaves
    
    @property
    def days_on_leave(self):
        """Calculate total leave days (paid + unpaid)."""
        return self.paid_leave_days + self.unpaid_leaves
    
    @property
    def attendance_percentage(self):
        """Calculate attendance percentage."""
        total_expected_days = (
            self.present_days + self.absent_days + self.paid_leave_days +
            self.half_day_count + self.weekly_Offs + self.unpaid_leaves
        )
        if total_expected_days == 0:
            return Decimal('0.00')
        return (self.total_days_worked / total_expected_days * 100).quantize(
            Decimal('0.01')
        )
    
    