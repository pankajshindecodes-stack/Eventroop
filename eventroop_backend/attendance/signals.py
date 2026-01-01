# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from attendance.models import Attendance
from attendance.models import AttendanceReport
from attendance.utils import PayrollCalculator


@receiver(post_save, sender=Attendance)
def update_attendance_report_on_save(sender, instance, created, **kwargs):
    """
    When attendance is created or updated, recalculate and save the report
    for that period for that user.
    """
    user = instance.user
    attendance_date = instance.date
    
    # Calculate payroll for the period containing this attendance date
    payroll = PayrollCalculator(user, base_date=attendance_date)
    reports = payroll.calculate_all_periods_auto(
        start_date=attendance_date,
        end_date=attendance_date
    )
    
    # Save/update the report for this period
    if reports:
        report = reports[0]
        AttendanceReport.objects.update_or_create(
            user=user,
            start_date=report["start_date"],
            end_date=report["end_date"],
            defaults={
                "present_days": report.get("present_days", 0),
                "absent_days": report.get("absent_days", 0),
                "half_day_count": report.get("half_day_count", 0),
                "paid_leave_days": report.get("paid_leave_days", 0),
                "weekly_Offs": report.get("weekly_Offs", 0),
                "unpaid_leaves": report.get("unpaid_leaves", 0),
                "total_payable_days": report.get("total_payable_days", 0),
                "total_payable_hours": report.get("total_payable_hours", 0),
                "salary_type": report.get("salary_type"),
                "final_salary": report.get("final_salary", 0),
                "daily_rate": report.get("daily_rate", 0),
                "current_payment": report.get("current_payment", 0),
            }
        )
    
    # Invalidate API cache for this user
    cache_key = f"attendance_reports_{user.id}"
    cache.delete(cache_key)


@receiver(post_delete, sender=Attendance)
def update_attendance_report_on_delete(sender, instance, **kwargs):
    """
    When attendance is deleted, recalculate and save the report
    for that period for that user.
    """
    user = instance.user
    attendance_date = instance.date
    
    # Calculate payroll for the period containing this attendance date
    payroll = PayrollCalculator(user, base_date=attendance_date)
    reports = payroll.calculate_all_periods_auto(
        start_date=attendance_date,
        end_date=attendance_date
    )
    
    # Save/update the report for this period
    if reports:
        report = reports[0]
        AttendanceReport.objects.update_or_create(
            user=user,
            start_date=report["start_date"],
            end_date=report["end_date"],
            defaults={
                "present_days": report.get("present_days", 0),
                "absent_days": report.get("absent_days", 0),
                "half_day_count": report.get("half_day_count", 0),
                "paid_leave_days": report.get("paid_leave_days", 0),
                "weekly_Offs": report.get("weekly_Offs", 0),
                "unpaid_leaves": report.get("unpaid_leaves", 0),
                "total_payable_days": report.get("total_payable_days", 0),
                "total_payable_hours": report.get("total_payable_hours", 0),
                "salary_type": report.get("salary_type"),
                "final_salary": report.get("final_salary", 0),
                "daily_rate": report.get("daily_rate", 0),
                "current_payment": report.get("current_payment", 0),
            }
        )
    
    # Invalidate API cache for this user
    cache_key = f"attendance_reports_{user.id}"
    cache.delete(cache_key)

