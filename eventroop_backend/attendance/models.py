from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
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
    Default status is PRESENT.
    """

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="attendance",
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER","VSRE_STAFF"]}
    )

    date = models.DateField(default=timezone.now)

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

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.date} ({self.status.label})"
