from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from .models import SalaryStructure
from attendance.models import TotalAttendance


# -------------------------------------------
# Salary Calculation
# -------------------------------------------
def calculate_salary(user, total_attendance):
    salary = SalaryStructure.objects.filter(user=user).first()
    if not salary:
        return Decimal("0")

    salary_type = salary.salary_type
    payable_days = total_attendance.payable_days
    payable_hours = total_attendance.total_payable_hours

    amount = Decimal("0")

    # --------------------------
    # Salary logic
    # --------------------------
    if salary_type == "HOURLY":
        amount = salary.rate * payable_hours

    elif salary_type == "DAILY":
        amount = salary.rate * payable_days

    elif salary_type == "WEEKLY":
        amount = salary.rate * (Decimal(payable_days) / Decimal("7"))

    elif salary_type == "FORTNIGHTLY":
        amount = salary.rate * (Decimal(payable_days) / Decimal("14"))

    elif salary_type == "MONTHLY":
        # Convert monthly salary → daily
        daily_rate = salary.rate / Decimal("30")
        amount = daily_rate * payable_days

    # Update both SalaryStructure and optionally TotalAttendance
    salary.total_salary = amount
    salary.save()

    total_attendance.salary_amount = amount
    total_attendance.save()

    return amount


# -------------------------------------------
# Trigger: Update salary when TotalAttendance changes
# -------------------------------------------
@receiver(post_save, sender=TotalAttendance)
def update_salary_on_attendance(sender, instance, **kwargs):
    """
    Whenever attendance totals update, auto-calculate salary.
    """
    calculate_salary(instance.user, instance)


# -------------------------------------------
# Trigger: Update salary when SalaryStructure changes
# -------------------------------------------
@receiver(post_save, sender=SalaryStructure)
def update_salary_on_structure_change(sender, instance, **kwargs):
    """
    If salary details change (like rate or salary_type),
    recalculate salary using existing attendance.
    """
    if hasattr(instance.user, "total_attendance"):
        attendance = instance.user.total_attendance
        calculate_salary(instance.user, attendance)
