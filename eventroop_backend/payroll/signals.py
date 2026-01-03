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
