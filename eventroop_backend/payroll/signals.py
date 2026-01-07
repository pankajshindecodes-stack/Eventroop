from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import SalaryStructure, SalaryReport
from .utils import SalaryCalculator
from attendance.models import AttendanceReport
from decimal import Decimal


def calculate_final_salary(record, previous_salary):
    """Calculate final_salary based on change_type and previous salary."""
    if record.change_type == "BASE_SALARY":
        return record.amount
    elif record.change_type == "INCREMENT":
        return previous_salary + record.amount
    elif record.change_type in ["ADVANCE", "LOAN"]:
        return previous_salary
    return previous_salary


def get_previous_salary(user, effective_from, exclude_pk=None):
    """Get the final_salary from the most recent previous record."""
    query = SalaryStructure.objects.filter(
        user=user,
        effective_from__lt=effective_from
    ).order_by("-effective_from")
    
    if exclude_pk:
        query = query.exclude(pk=exclude_pk)
    
    previous = query.first()
    return previous.final_salary if previous else Decimal(0)


def recalculate_subsequent_salaries(user, effective_from):
    """
    Recalculate final_salary for all records after effective_from.
    Returns list of (record_pk, new_final_salary) tuples for bulk update.
    """
    subsequent_records = (
        SalaryStructure.objects
        .filter(user=user, effective_from__gt=effective_from)
        .order_by("effective_from")
        .values_list('pk', 'change_type', 'amount')
    )
    
    if not subsequent_records:
        return []
    
    updates = []
    current_salary = get_previous_salary(user, effective_from)
    
    for pk, change_type, amount in subsequent_records:
        new_salary = calculate_final_salary(
            type('obj', (), {'change_type': change_type, 'amount': amount})(),
            current_salary
        )
        updates.append((pk, new_salary))
        current_salary = new_salary
    
    return updates


def bulk_update_salaries(updates):
    """Perform bulk update of salary records to avoid N+1 queries."""
    if not updates:
        return
    
    with transaction.atomic():
        for pk, final_salary in updates:
            SalaryStructure.objects.filter(pk=pk).update(
                final_salary=final_salary
            )


def recalculate_affected_salary_reports(user, effective_from):
    """
    Recalculate SalaryReport for unpaid records affected by salary change.
    Only updates if total_payable > 0.
    """
    affected_reports = AttendanceReport.objects.filter(
        user=user,
        end_date__gte=effective_from
    ).select_related('user')  # Optimize if needed
    
    if not affected_reports.exists():
        return
    
    # Get all paid salary records at once to avoid N+1
    paid_salary_dates = set(
        SalaryReport.objects
        .filter(user=user, paid_amount__gt=0)
        .values_list('start_date', 'end_date')
    )
    
    calculator = SalaryCalculator(user=user)
    updates = []
    
    for report in affected_reports:
        # Skip already paid salaries
        if (report.start_date, report.end_date) in paid_salary_dates:
            continue
        
        payroll = calculator.calculate_payroll(
            base_date=report.end_date,
            period_type=report.period_type
        )
        total_payable = Decimal(str(payroll.get("current_payment", 0)))
        
        if total_payable <= 0:
            continue
        
        daily_rate = Decimal(str(payroll.get("daily_rate", 0)))
        updates.append({
            'user': user,
            'start_date': report.start_date,
            'end_date': report.end_date,
            'total_payable_amount': total_payable,
            'daily_rate': daily_rate,
        })
    
    # Bulk update or create
    if updates:
        with transaction.atomic():
            for update_data in updates:
                SalaryReport.objects.update_or_create(
                    user=update_data['user'],
                    start_date=update_data['start_date'],
                    end_date=update_data['end_date'],
                    defaults={
                        'total_payable_amount': update_data['total_payable_amount'],
                        'daily_rate': update_data['daily_rate'],
                    }
                )


@receiver(post_save, sender=SalaryStructure)
def update_salary_on_change(sender, instance, created, **kwargs):
    """
    Recalculate final_salary for all entries after the updated entry.
    Triggered when a SalaryStructure is saved (created or updated).
    """
    if created:
        return
    
    updates = recalculate_subsequent_salaries(instance.user, instance.effective_from)
    bulk_update_salaries(updates)


@receiver(post_delete, sender=SalaryStructure)
def update_salary_on_delete(sender, instance, **kwargs):
    """
    Recalculate final_salary for all entries after the deleted entry.
    Triggered when a SalaryStructure is deleted.
    """
    updates = recalculate_subsequent_salaries(instance.user, instance.effective_from)
    bulk_update_salaries(updates)


@receiver(post_save, sender=SalaryStructure)
def update_salary_reports_on_salary_change(sender, instance, **kwargs):
    """
    Recalculate SalaryReport when SalaryStructure changes.
    Updates only unpaid salary reports for affected periods.
    """
    recalculate_affected_salary_reports(instance.user, instance.effective_from)