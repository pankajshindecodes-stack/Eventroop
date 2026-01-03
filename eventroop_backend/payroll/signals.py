from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import SalaryStructure,SalaryTransaction
from .utils import SalaryCalculator
from attendance.models import AttendanceReport
from decimal import Decimal

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


@receiver(post_save, sender=SalaryStructure)
def update_salary_transactions_on_salary_change(sender, instance, **kwargs):
    """
    Recalculate SalaryTransaction when SalaryStructure changes.
    """

    user = instance.user
    effective_from = instance.effective_from

    # Find attendance reports affected by this salary change
    affected_reports = AttendanceReport.objects.filter(
        user=user,
        end_date__gte=effective_from
    )

    calculator = SalaryCalculator(user=user)

    for report in affected_reports:
        # Skip already paid salaries (VERY IMPORTANT)
        txn = SalaryTransaction.objects.filter(
            user=user,
            payment_period_start=report.start_date,
            payment_period_end=report.end_date,
            status="SUCCESS"
        ).first()

        if txn:
            continue  # Never touch paid payrolls

        payroll = calculator.calculate_payroll(
            base_date=report.end_date,
            period_type=report.period_type
        )

        total_payable = Decimal(str(payroll["current_payment"]))
        daily_rate = Decimal(str(payroll["daily_rate"]))

        if total_payable <= 0:
            continue

        SalaryTransaction.objects.update_or_create(
            user=user,
            payment_period_start=report.start_date,
            payment_period_end=report.end_date,
            defaults={
                "total_payable_amount": total_payable,
                "daily_rate": daily_rate,
                "remaining_payment": total_payable,
            }
        )
