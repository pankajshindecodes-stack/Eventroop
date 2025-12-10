from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
from datetime import timedelta

from .models import Attendance, TotalAttendance


@receiver(post_save, sender=Attendance)
def update_total_attendance(sender, instance, **kwargs):
    user = instance.user
    today = instance.date

    # --- DAILY TOTAL ---
    total_day = (
        Attendance.objects.filter(user=user, date=today)
        .aggregate(total=Sum("duration"))["total"] or timedelta()
    )
    total_day_hours = round(total_day.total_seconds() / 3600, 2)

    # --- WEEKLY TOTAL (Mon–Sun) ---
    start_week = today - timedelta(days=today.weekday())  # Monday
    end_week = start_week + timedelta(days=6)              # Sunday

    total_week = (
        Attendance.objects.filter(user=user, date__range=[start_week, end_week])
        .aggregate(total=Sum("duration"))["total"] or timedelta()
    )
    total_week_hours = round(total_week.total_seconds() / 3600, 2)

    # --- FORTNIGHT TOTAL (last 14 days) ---
    start_fortnight = today - timedelta(days=13)

    total_fortnight = (
        Attendance.objects.filter(user=user, date__range=[start_fortnight, today])
        .aggregate(total=Sum("duration"))["total"] or timedelta()
    )
    total_fortnight_hours = round(total_fortnight.total_seconds() / 3600, 2)

    # --- MONTH TOTAL ---
    start_month = today.replace(day=1)
    end_month = (start_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)

    total_month = (
        Attendance.objects.filter(user=user, date__range=[start_month, end_month])
        .aggregate(total=Sum("duration"))["total"] or timedelta()
    )
    total_month_hours = round(total_month.total_seconds() / 3600, 2)

    # --- SAVE OR UPDATE TotalAttendance ---
    TotalAttendance.objects.update_or_create(
        user=user,
        defaults={
            "total_hours_day": total_day_hours,
            "total_hours_week": total_week_hours,
            "total_hours_fortnight": total_fortnight_hours,
            "total_hours_month": total_month_hours,
        }
    )
