from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from decimal import Decimal

from .models import Attendance, AttendanceReport
from payroll.models import SalaryStructure,SalaryTransaction
from .utils import AttendanceCalculator
from payroll.utils import SalaryCalculator

@receiver(post_save, sender=Attendance)
def update_attendance_report_on_save(sender, instance, created, **kwargs):
    """
    When attendance is created or updated, recalculate and save the report
    for that period for that user.
    """
    user = instance.user
    attendance_date = instance.date
    salary_structure = (
            SalaryStructure.objects
            .filter(user=user, effective_from__lte=attendance_date)
            .order_by("-effective_from")
            .first()
        )
    period_type = salary_structure.salary_type if salary_structure else None
    # Initialize the calculator with the attendance date
    calculator = AttendanceCalculator(user, base_date=attendance_date)
    
    # Get report for the period containing this attendance date
    # Default to MONTHLY if no specific period type is needed
    report = calculator.get_attendance_report(
        base_date=attendance_date,
        period_type=period_type
    )
    
    if report:
        # Save/update the report for this period
        AttendanceReport.objects.update_or_create(
            user=user,
            start_date=report["start_date"],
            end_date=report["end_date"],
            period_type=report["period_type"],
            defaults={
                "present_days": Decimal(str(report.get("present_days", 0))),
                "absent_days": Decimal(str(report.get("absent_days", 0))),
                "half_day_count": Decimal(str(report.get("half_day_count", 0))),
                "paid_leave_days": Decimal(str(report.get("paid_leave_days", 0))),
                "weekly_Offs": Decimal(str(report.get("weekly_offs", 0))),
                "unpaid_leaves": Decimal(str(report.get("unpaid_leaves", 0))),
                "total_payable_days": Decimal(str(report.get("total_payable_days", 0))),
                "total_payable_hours": Decimal(str(report.get("total_payable_hours", 0))),
            }
        )
    
    # Invalidate cache for this user's attendance reports
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
    
    salary_structure = (
            SalaryStructure.objects
            .filter(user=user, effective_from__lte=attendance_date)
            .order_by("-effective_from")
            .first()
        )
    period_type = salary_structure.salary_type if salary_structure else None
    
    # Initialize the calculator with the attendance date
    calculator = AttendanceCalculator(user, base_date=attendance_date)
    # Get report for the period containing this attendance date
    # Default to MONTHLY if no specific period type is needed
    report = calculator.get_attendance_report(
        base_date=attendance_date,
        period_type=period_type
    )
    
    if report:
        # Save/update the report for this period
        AttendanceReport.objects.update_or_create(
            user=user,
            start_date=report["start_date"],
            end_date=report["end_date"],
            period_type=report["period_type"],
            defaults={
                "present_days": Decimal(str(report.get("present_days", 0))),
                "absent_days": Decimal(str(report.get("absent_days", 0))),
                "half_day_count": Decimal(str(report.get("half_day_count", 0))),
                "paid_leave_days": Decimal(str(report.get("paid_leave_days", 0))),
                "weekly_Offs": Decimal(str(report.get("weekly_offs", 0))),
                "unpaid_leaves": Decimal(str(report.get("unpaid_leaves", 0))),
                "total_payable_days": Decimal(str(report.get("total_payable_days", 0))),
                "total_payable_hours": Decimal(str(report.get("total_payable_hours", 0))),
            }
        )
    
    # Invalidate cache for this user's attendance reports
    cache_key = f"attendance_reports_{user.id}"
    cache.delete(cache_key)


@receiver(post_save, sender=AttendanceReport)
def create_or_update_salary_transaction(sender, instance, **kwargs):
    """
    Auto-create or update SalaryTransaction whenever
    AttendanceReport is created or updated.
    """

    user = instance.user
    period_start = instance.start_date
    period_end = instance.end_date
    period_type = instance.period_type

    # Initialize salary calculator
    calculator = SalaryCalculator(user=user, base_date=period_end)

    # Calculate payroll
    payroll_data = calculator.calculate_payroll(
        base_date=period_end,
        period_type=period_type
    )

    total_payable_amount = Decimal(str(payroll_data.get("current_payment", 0)))
    daily_rate = Decimal(str(payroll_data.get("daily_rate", 0)))

    if total_payable_amount <= 0:
        return  # Do not create zero or negative salary transactions

    # Create or update SalaryTransaction
    SalaryTransaction.objects.update_or_create(
        user=user,
        payment_period_start=period_start,
        payment_period_end=period_end,
        defaults={
            "total_payable_amount": total_payable_amount,
            "daily_rate": daily_rate,
            "remaining_payment": total_payable_amount,
        }
    )
