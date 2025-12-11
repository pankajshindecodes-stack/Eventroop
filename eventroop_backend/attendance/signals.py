from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from decimal import Decimal
from datetime import timedelta

from .models import Attendance, TotalAttendance, AttendanceStatus


# -------------------------------------------
# Convert timedelta → decimal hours
# -------------------------------------------
def duration_to_hours(duration: timedelta) -> Decimal:
    if not duration:
        return Decimal("0")
    return Decimal(duration.total_seconds()) / Decimal(3600)


# -------------------------------------------
# Attendance Aggregation Logic
# -------------------------------------------
def update_total_attendance(user):
    records = Attendance.objects.filter(user=user)

    # Status codes
    present_status = AttendanceStatus.objects.filter(code__iexact="P").first()
    absent_status = AttendanceStatus.objects.filter(code__iexact="A").first()
    half_day_status = AttendanceStatus.objects.filter(code__iexact="HD").first()
    paid_leave_status = AttendanceStatus.objects.filter(code__iexact="PL").first()

    # Count statuses
    present_days = records.filter(status=present_status).count() if present_status else 0
    absent_days = records.filter(status=absent_status).count() if absent_status else 0
    half_day_days = records.filter(status=half_day_status).count() if half_day_status else 0
    paid_leave_days = records.filter(status=paid_leave_status).count() if paid_leave_status else 0

    # Total hours
    duration_sum = records.aggregate(total=Sum("duration"))["total"]
    total_seconds = duration_sum.total_seconds() if duration_sum else 0
    total_hours = Decimal(total_seconds) / Decimal(3600)

    # Payable days formula
    payable_days = (
        present_days +
        paid_leave_days +
        (Decimal("0.5") * half_day_days)
    )

    # Create/update TotalAttendance
    total, created = TotalAttendance.objects.get_or_create(user=user)

    total.present_days = present_days
    total.absent_days = absent_days
    total.half_day_count = half_day_days
    total.paid_leave_days = paid_leave_days

    total.total_payable_hours = total_hours
    total.payable_days = payable_days
    total.total_payable_days = payable_days

    total.save()

# -------------------------------------------
# Signals
# -------------------------------------------
@receiver(post_save, sender=Attendance)
def attendance_saved(sender, instance, **kwargs):
    update_total_attendance(instance.user)


@receiver(post_delete, sender=Attendance)
def attendance_deleted(sender, instance, **kwargs):
    update_total_attendance(instance.user)
