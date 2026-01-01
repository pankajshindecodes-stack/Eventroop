# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from .models import SalaryStructure
from attendance.utils import PayrollCalculator
from attendance.models import AttendanceReport
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=SalaryStructure)
def update_attendance_report_on_salary_structure_change(sender, instance, created, **kwargs):
    """
    Signal triggered when a SalaryStructure record is created or updated.
    Regenerates all attendance reports from the effective_from date onwards for the user.
    """
    try:
        user = instance.user
        effective_from = instance.effective_from
        
        logger.info(
            f"{'Created' if created else 'Updated'} salary structure for user {user.id} "
            f"effective from {effective_from}. Regenerating all reports from this date."
        )
        
        # Regenerate all reports from the effective date onwards
        generate_all_reports_from_date(user, effective_from)
        
    except Exception as e:
        logger.error(
            f"Error updating attendance reports on salary structure change: {str(e)}",
            exc_info=True
        )


def get_report_period(date_obj):
    """
    Determine the start and end date of the report period for a given date.
    Assumes reports are monthly (from 1st to last day of the month).
    Adjust this logic based on your payroll period definition.
    
    Args:
        date_obj: The date to find the period for
        
    Returns:
        Tuple of (start_date, end_date)
    """
    # Monthly period: 1st to last day of month
    start_date = date_obj.replace(day=1)
    
    # Get last day of month
    next_month = start_date + timedelta(days=32)
    end_date = (next_month.replace(day=1) - timedelta(days=1))
    
    return start_date, end_date


def generate_attendance_report_for_period(user, start_date, end_date):
    """
    Generate and store attendance report for a specific period.
    
    Args:
        user: CustomUser instance
        start_date: Period start date
        end_date: Period end date
    """
    try:
        payroll = PayrollCalculator(user)
        
        # Calculate report for this specific period
        reports_data = payroll.calculate_all_periods_auto(
            start_date=start_date,
            end_date=end_date
        )
        
        if not reports_data:
            logger.warning(f"No reports generated for user {user.id} ({start_date} to {end_date})")
            return
        
        # Save the report (should be only one for the period)
        for report_data in reports_data:
            _save_attendance_report(user, report_data)
            
    except Exception as e:
        logger.error(
            f"Error generating attendance report for user {user.id} "
            f"({start_date} to {end_date}): {str(e)}",
            exc_info=True
        )
        raise


def generate_all_reports_from_date(user, from_date):
    """
    Generate and store all attendance reports from a given date onwards.
    Useful when salary structure changes and affects multiple periods.
    
    Args:
        user: CustomUser instance
        from_date: Start date for report regeneration
    """
    try:
        payroll = PayrollCalculator(user)
        
        # Calculate all reports from the given date to today
        reports_data = payroll.calculate_all_periods_auto(
            start_date=from_date,
            end_date=timezone.now().date()
        )
        
        if not reports_data:
            logger.warning(f"No reports generated for user {user.id} from {from_date} onwards")
            return
        
        # Save all reports
        for report_data in reports_data:
            _save_attendance_report(user, report_data)
        
        logger.info(f"Regenerated {len(reports_data)} reports for user {user.id} from {from_date}")
            
    except Exception as e:
        logger.error(
            f"Error generating reports from {from_date} for user {user.id}: {str(e)}",
            exc_info=True
        )
        raise


def _save_attendance_report(user, report_data):
    """
    Save individual attendance report to database.
    Uses get_or_create with update to handle duplicates gracefully.
    
    report_data should contain:
    {
        'start_date': date,
        'end_date': date,
        'attendance': {...},
        'salary': {...},
    }
    """
    start_date = report_data.get('start_date')
    end_date = report_data.get('end_date')
    
    if not start_date or not end_date:
        logger.warning(f"Missing date range in report_data for user {user.id}")
        return
    
    attendance = report_data.get('attendance', {})
    salary = report_data.get('salary', {})
    
    # Extract and convert values with defaults
    report_fields = {
        'present_days': Decimal(str(attendance.get('present_days', 0))),
        'absent_days': Decimal(str(attendance.get('absent_days', 0))),
        'half_day_count': Decimal(str(attendance.get('half_day_count', 0))),
        'paid_leave_days': Decimal(str(attendance.get('paid_leave_days', 0))),
        'weekly_Offs': Decimal(str(attendance.get('weekly_offs', 0))),
        'unpaid_leaves': Decimal(str(attendance.get('unpaid_leaves', 0))),
        'total_payable_days': Decimal(str(attendance.get('total_payable_days', 0))),
        'total_payable_hours': Decimal(str(attendance.get('total_payable_hours', 0))),
        
        'salary_type': salary.get('salary_type', ''),
        'final_salary': Decimal(str(salary.get('final_salary', 0))),
        'daily_rate': Decimal(str(salary.get('daily_rate', 0))),
        'current_payment': Decimal(str(salary.get('current_payment', 0))),
        'remaining_payable_days': Decimal(str(salary.get('remaining_payable_days', 0))),
        'remaining_payment': Decimal(str(salary.get('remaining_payment', 0))),
    }
    
    # Use get_or_create to avoid duplicates
    report, created = AttendanceReport.objects.get_or_create(
        user=user,
        start_date=start_date,
        end_date=end_date,
        defaults=report_fields
    )
    
    if not created:
        # Update existing report
        for field, value in report_fields.items():
            setattr(report, field, value)
        report.save(update_fields=list(report_fields.keys()))
        logger.info(f"Updated report for {user.id} ({start_date} to {end_date})")
    else:
        logger.info(f"Created report for {user.id} ({start_date} to {end_date})")





from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import SalaryStructure


@receiver(post_save, sender=SalaryStructure)
def update_salary_on_change(sender, instance, created, **kwargs):
    """
    Signal to recalculate final_salary for all entries after the updated entry.
    Triggered when a SalaryStructure is saved (created or updated).
    """
    if created:
        # If it's a new entry, no need to update anything
        return

    # Get all salary records after this entry's effective date
    subsequent_records = (
        SalaryStructure.objects
        .filter(user=instance.user, effective_from__gt=instance.effective_from)
        .order_by("effective_from")
    )

    # Recalculate final_salary for all subsequent records
    with transaction.atomic():
        for record in subsequent_records:
            # Get the previous record
            previous = (
                SalaryStructure.objects
                .filter(
                    user=record.user,
                    effective_from__lt=record.effective_from
                )
                .exclude(pk=record.pk)
                .order_by("-effective_from")
                .first()
            )

            previous_salary = previous.final_salary if previous else 0

            # Recalculate based on change type
            if record.change_type == "BASE_SALARY":
                record.final_salary = record.amount
            elif record.change_type == "INCREMENT":
                record.final_salary = previous_salary + record.amount
            elif record.change_type in ["ADVANCE", "LOAN"]:
                record.final_salary = previous_salary

            # Save without triggering signals again
            SalaryStructure.objects.filter(pk=record.pk).update(
                final_salary=record.final_salary
            )


@receiver(post_delete, sender=SalaryStructure)
def update_salary_on_delete(sender, instance, **kwargs):
    """
    Signal to recalculate final_salary for all entries after the deleted entry.
    Triggered when a SalaryStructure is deleted.
    """
    # Get all salary records after the deleted entry's effective date
    subsequent_records = (
        SalaryStructure.objects
        .filter(user=instance.user, effective_from__gt=instance.effective_from)
        .order_by("effective_from")
    )

    # Recalculate final_salary for all subsequent records
    with transaction.atomic():
        for record in subsequent_records:
            # Get the previous record
            previous = (
                SalaryStructure.objects
                .filter(
                    user=record.user,
                    effective_from__lt=record.effective_from
                )
                .order_by("-effective_from")
                .first()
            )

            previous_salary = previous.final_salary if previous else 0

            # Recalculate based on change type
            if record.change_type == "BASE_SALARY":
                record.final_salary = record.amount
            elif record.change_type == "INCREMENT":
                record.final_salary = previous_salary + record.amount
            elif record.change_type in ["ADVANCE", "LOAN"]:
                record.final_salary = previous_salary

            # Save without triggering signals again
            SalaryStructure.objects.filter(pk=record.pk).update(
                final_salary=record.final_salary
            )

