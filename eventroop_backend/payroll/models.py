from django.db import models
from accounts.models import CustomUser


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

    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="payments_made",
        limit_choices_to={"user_type": "VSRE_OWNER"}
    )

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

    # Useful if you want to track salary month (optional)
    salary_month = models.DateField(null=True, blank=True)

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
