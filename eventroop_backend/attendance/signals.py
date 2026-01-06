from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from decimal import Decimal
from .models import Attendance, AttendanceReport
from payroll.models import SalaryStructure, SalaryReport
from .utils import AttendanceCalculator
from payroll.utils import SalaryCalculator

@receiver(post_save, sender=Attendance)
def update_attendance_report_on_save(sender, instance, created, **kwargs):
    """
    When attendance is created or updated, recalculate and save the report
    for that period for that user.
    """
    try:
        user = instance.user
        attendance_date = instance.date
        salary_structure = SalaryStructure.objects.filter(user=user,change_type__in=["BASE_SALARY","INCREMENT"]).order_by("-effective_from").first()
        period_type = salary_structure.salary_type if salary_structure else "MONTHLY"
        
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
                    "weekly_Offs": Decimal(str(report.get("weekly_offs", 0))),
                    "unpaid_leaves": Decimal(str(report.get("unpaid_leaves", 0))),
                    "total_payable_days": Decimal(str(report.get("total_payable_days", 0))),
                    "total_payable_hours": Decimal(str(report.get("total_payable_hours", 0))),
                }
            )
        
        cache_key = f"attendance_reports_{user.id}"
        cache.delete(cache_key)
    except Exception as e:
        pass


@receiver(post_delete, sender=Attendance)
def update_attendance_report_on_delete(sender, instance, **kwargs):
    """
    When attendance is deleted, recalculate and save the report
    for that period for that user.
    """
    try:
        user = instance.user
        attendance_date = instance.date
        
        salary_structure = (
                SalaryStructure.objects
                .filter(
                    user=user,
                    effective_from__lte=attendance_date,
                    change_type__in=["BASE_SALARY","INCREMENT"]
                )
                .order_by("-effective_from")
                .first()
            )
        period_type = salary_structure.salary_type if salary_structure else "MONTHLY"
        
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
                    "weekly_Offs": Decimal(str(report.get("weekly_offs", 0))),
                    "unpaid_leaves": Decimal(str(report.get("unpaid_leaves", 0))),
                    "total_payable_days": Decimal(str(report.get("total_payable_days", 0))),
                    "total_payable_hours": Decimal(str(report.get("total_payable_hours", 0))),
                }
            )
        
        cache_key = f"attendance_reports_{user.id}"
        cache.delete(cache_key)
    except Exception as e:
        pass


@receiver(post_save, sender=AttendanceReport)
def create_or_update_salary_report_on_attendance(sender, instance, created, **kwargs):
    """
    Auto-create or update SalaryReport whenever
    AttendanceReport is created or updated.
    """
    try:
        user = instance.user
        period_start = instance.start_date
        period_end = instance.end_date
        period_type = instance.period_type

        calculator = SalaryCalculator(user=user, base_date=period_end)

        payroll_data = calculator.calculate_payroll(
            base_date=period_end,
            period_type=period_type
        )

        total_payable_amount = Decimal(str(payroll_data.get("current_payment", 0)))
        daily_rate = Decimal(str(payroll_data.get("daily_rate", 0)))

        if total_payable_amount <= 0:
            return

        # Check if already paid
        existing_report = SalaryReport.objects.filter(
            user=user,
            start_date=period_start,
            end_date=period_end
        ).first()

        if existing_report and existing_report.paid_amount > 0:
            return

        SalaryReport.objects.update_or_create(
            user=user,
            start_date=period_start,
            end_date=period_end,
            defaults={
                "total_payable_amount": total_payable_amount,
                "daily_rate": daily_rate,
                # remaining_payment is auto-calculated in model's save()
            }
        )
    except Exception as e:
        pass