# signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from decimal import Decimal
from datetime import timedelta
from .models import Attendance, AttendanceReport
from .utils import PayrollCalculator
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Attendance)
def update_attendance_report_on_save(sender, instance, created, **kwargs):
    """
    Signal triggered when an Attendance record is created or updated.
    Regenerates the attendance report for the affected period.
    """
    try:
        user = instance.user
        attendance_date = instance.date
        
        # Find the period this attendance belongs to
        start_date, end_date = get_report_period(attendance_date)
        
        logger.info(
            f"{'Created' if created else 'Updated'} attendance for user {user.id} "
            f"on {attendance_date}. Updating report for {start_date} to {end_date}"
        )
        
        # Regenerate the report for this period
        generate_attendance_report_for_period(user, start_date, end_date)
        
    except Exception as e:
        logger.error(f"Error updating attendance report on save: {str(e)}", exc_info=True)


@receiver(post_delete, sender=Attendance)
def update_attendance_report_on_delete(sender, instance, **kwargs):
    """
    Signal triggered when an Attendance record is deleted.
    Regenerates the attendance report for the affected period.
    """
    try:
        user = instance.user
        attendance_date = instance.attendance_date
        
        # Find the period this attendance belonged to
        start_date, end_date = get_report_period(attendance_date)
        
        logger.info(
            f"Deleted attendance for user {user.id} on {attendance_date}. "
            f"Updating report for {start_date} to {end_date}"
        )
        
        # Regenerate the report for this period
        generate_attendance_report_for_period(user, start_date, end_date)
        
    except Exception as e:
        logger.error(f"Error updating attendance report on delete: {str(e)}", exc_info=True)


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

