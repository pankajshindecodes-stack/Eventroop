from django.db import models
from accounts.models import CustomUser

class SalaryStructure(models.Model):
    SALARY_TYPE_CHOICES = [
        ("HOURLY", "Hourly"),
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("FORTNIGHTLY", "Fortnightly"),
        ("MONTHLY", "Monthly"),
    ]

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="salary_structure",
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER", "VSRE_STAFF"]}
    )

    salary_type = models.CharField(max_length=20, choices=SALARY_TYPE_CHOICES, default="MONTHLY")

    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    total_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def calculate_salary(self, attendance):
        """
        attendance = TotalAttendance instance
        """
        st = self.salary_type

        if st == "HOURLY":
            return (attendance.total_hours_day or 0) * (self.rate or 0)

        if st == "DAILY":
            return (self.rate or 0)

        if st == "WEEKLY":
            return (self.rate or 0)

        if st == "FORTNIGHTLY":
            return (self.rate or 0)

        if st == "MONTHLY":
            return (self.rate or 0)

        return 0

    def __str__(self):
        return f"Salary Structure for {self.user.get_full_name()}"

class PayRollPayment(models.Model):

    PAYMENT_TYPE_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("FORTNIGHTLY", "Fortnightly"),
        ("WEEKLY", "Weekly"),
        ("DAILY", "Daily"),
        ("HOURLY", "Hourly"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    receiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="payments_received",
        limit_choices_to={"user_type__in": ["VSRE_STAFF", "VSRE_MANAGER"]},
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    note = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to="payment_receipts/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.owner} → {self.receiver} ({self.payment_type})"
