from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from decimal import Decimal
from .models import Attendance, AttendanceReport
from payroll.models import SalaryStructure, SalaryReport
from .utils import AttendanceCalculator
from payroll.utils import SalaryCalculator


def get_period_type(user, attendance_date):
    """Helper to get period type for a user and date."""
    salary_structure = (
        SalaryStructure.objects
        .filter(
            user=user,
            effective_from__lte=attendance_date,
            change_type__in=["BASE_SALARY", "INCREMENT"]
        )
        .order_by("-effective_from")
        .first()
    )
    return salary_structure.salary_type if salary_structure else "MONTHLY"


def update_attendance_report(user, attendance_date):
    """Extract common attendance report update logic."""
    try:
        period_type = get_period_type(user, attendance_date)
        calculator = AttendanceCalculator(user, base_date=attendance_date)
        
        report = calculator.get_attendance_report(
            base_date=attendance_date,
            period_type=period_type
        )
        
        if report:
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
                    "weekly_Offs": Decimal(str(report.get("weekly_Offs", 0))),
                    "unpaid_leaves": Decimal(str(report.get("unpaid_leaves", 0))),
                    "total_payable_days": Decimal(str(report.get("total_payable_days", 0))),
                    "total_payable_hours": Decimal(str(report.get("total_payable_hours", 0))),
                }
            )
        return report
    except Exception as e:
        print(f"Error updating attendance report: {e}")
        return None


def update_salary_report(user, period_start, period_end, period_type):
    """Extract common salary report update logic."""
    try:
        calculator = SalaryCalculator(user=user, base_date=period_end)
        
        payroll_data = calculator.calculate_payroll(
            base_date=period_end,
            period_type=period_type
        )

        total_payable_amount = Decimal(str(payroll_data.get("current_payment", 0)))
        daily_rate = Decimal(str(payroll_data.get("daily_rate", 0)))

        # Check if already paid
        existing_report = SalaryReport.objects.filter(
            user=user,
            start_date=period_start,
            end_date=period_end
        ).first()
        
        remaining_payment = 0 
        if existing_report: 
            remaining_payment = existing_report.total_payable_amount - existing_report.paid_amount
        
        instance, created = SalaryReport.objects.update_or_create(
            user=user,
            start_date=period_start,
            end_date=period_end,
            defaults={
                "total_payable_amount": total_payable_amount,
                "daily_rate": daily_rate,
                "remaining_payment": remaining_payment
            }
        )
    except Exception as e:
        print(f"Error updating salary report: {e}")


def clear_cache(user_id):
    """Clear attendance cache for user."""
    cache_key = f"attendance_reports_{user_id}"
    cache.delete(cache_key)


@receiver(post_save, sender=Attendance)
def update_attendance_report_on_save(sender, instance, created, **kwargs):
    """When attendance is created or updated, recalculate and save the report."""
    user = instance.user
    attendance_date = instance.date
    
    report = update_attendance_report(user, attendance_date)
    
    if report:
        update_salary_report(
            user=user,
            period_start=report["start_date"],
            period_end=report["end_date"],
            period_type=report["period_type"]
        )
    
    clear_cache(user.id)


@receiver(post_save, sender=AttendanceReport)
def create_or_update_salary_report_on_attendance(sender, instance, created, **kwargs):
    """Auto-create or update SalaryReport when AttendanceReport changes."""
    update_salary_report(
        user=instance.user,
        period_start=instance.start_date,
        period_end=instance.end_date,
        period_type=instance.period_type
    )