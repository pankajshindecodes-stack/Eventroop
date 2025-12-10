from django.db.models.signals import pre_save,post_save
from django.dispatch import receiver
from .models import SalaryStructure
from attendance.models import TotalAttendance

@receiver(post_save, sender=TotalAttendance)
def update_salary_on_attendance(sender, instance, **kwargs):
    """
    Whenever attendance totals update, auto-calculate salary.
    """
    try:
        salary = SalaryStructure.objects.get(user=instance.user)
    except SalaryStructure.DoesNotExist:
        return  # salary not configured yet

    salary.total_salary = salary.calculate_salary(instance)
    salary.save()

@receiver(post_save, sender=SalaryStructure)
def update_salary_on_structure_change(sender, instance, **kwargs):
    """
    If salary details change (like rate or salary_type),
    recalculate salary using existing attendance.
    """
    if hasattr(instance.user, "total_attendance"):
        attendance = instance.user.total_attendance
        instance.total_salary = instance.calculate_salary(attendance)
        instance.save()
