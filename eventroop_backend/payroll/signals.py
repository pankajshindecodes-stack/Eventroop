# payroll/signal.py 
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from .models import SalaryStructure
from attendance.models import TotalAttendance


# -------------------------------------------
# Salary Calculation (No Saving)
# -------------------------------------------
def calculate_salary(user, total_attendance):
    """Calculate salary amount without saving to avoid signal recursion."""
    salary = SalaryStructure.objects.filter(user=50).first()
    if not salary:
        return Decimal("0")

    salary_type = salary.salary_type
    payable_days = total_attendance.total_payable_days
    payable_hours = total_attendance.total_payable_hours

    amount = Decimal("0")

    if salary_type == "HOURLY":
        amount = salary.rate * payable_hours
    elif salary_type == "DAILY":
        amount = salary.rate * payable_days
    elif salary_type == "WEEKLY":
        amount = salary.rate * (Decimal(payable_days) / Decimal("7"))
    elif salary_type == "FORTNIGHTLY":
        amount = salary.rate * (Decimal(payable_days) / Decimal("14"))
    elif salary_type == "MONTHLY":
        daily_rate = salary.rate / Decimal("30")
        amount = daily_rate * payable_days

    return amount


# -------------------------------------------
# Trigger: Update salary when TotalAttendance changes
# -------------------------------------------
@receiver(post_save, sender=TotalAttendance)
def update_salary_on_attendance(sender, instance, created=False, **kwargs):
    """
    Recalculate and update salary when attendance totals change.
    Only saves SalaryStructure, not TotalAttendance to prevent recursion.
    """
    amount = calculate_salary(instance.user, instance)
    
    salary = SalaryStructure.objects.filter(user=instance.user).first()
    if salary and salary.total_salary != amount:
        salary.total_salary = amount
        salary.save(update_fields=['total_salary'])


# -------------------------------------------
# Trigger: Update salary when SalaryStructure changes
# -------------------------------------------
@receiver(post_save, sender=SalaryStructure)
def update_salary_on_structure_change(sender, instance, **kwargs):
    """
    Recalculate salary when rate or salary_type changes.
    """
    try:
        total_attendance = TotalAttendance.objects.get(user=instance.user)
        amount = calculate_salary(instance.user, total_attendance)
        
        if instance.total_salary != amount:
            instance.total_salary = amount
            instance.save(update_fields=['total_salary'])
    except TotalAttendance.DoesNotExist:
        pass

