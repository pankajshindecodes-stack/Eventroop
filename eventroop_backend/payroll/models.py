from django.db import models
from accounts.models import CustomUser
from django.utils import timezone

class SalaryStructure(models.Model):
    SALARY_TYPE_CHOICES = [
        ("HOURLY", "Hourly"),
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("FORTNIGHTLY", "Fortnightly"),
        ("MONTHLY", "Monthly"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="salary_structures"
    )

    salary_type = models.CharField(max_length=20, choices=SALARY_TYPE_CHOICES, default="MONTHLY")
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_salary = models.DecimalField(max_digits=12, decimal_places=2)

    advance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_increment = models.BooleanField(default=False)

    effective_from = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ("user", "effective_from")

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.total_salary} from {self.effective_from}"

class SalaryTransaction(models.Model):
    """
    Payroll / Salary payment transaction
    """

    PAYMENT_TYPE_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("FORTNIGHTLY", "Fortnightly"),
        ("WEEKLY", "Weekly"),
        ("DAILY", "Daily"),
        ("HOURLY", "Hourly"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CHECK", "Check"),
        ("CASH", "Cash"),
        ("UPI", "UPI"),
        ("OTHER", "Other"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("CANCELLED", "Cancelled"),
    ]

    # Payroll identifiers
    transaction_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique salary transaction ID"
    )

    # Employee receiving salary
    receiver = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="salary_receiver"
    )

    # Employer / processor
    payer = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="salary_payer"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Salary amount"
    )

    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES
    )

    # Salary period
    payment_period_start = models.DateField()
    payment_period_end = models.DateField()

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="BANK_TRANSFER"
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Bank ref / UTR / cheque number"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True
    )

    note = models.TextField(blank=True, null=True)

    attachment = models.FileField(
        upload_to="salary_receipts/",
        blank=True,
        null=True
    )

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When salary was paid"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_period_start"]
        verbose_name = "Salary Payment"
        verbose_name_plural = "Salary Payments"
        indexes = [
            models.Index(fields=["receiver", "-processed_at"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["transaction_id"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(amount__gt=0),
                name="salary_amount_positive"
            ),
            models.CheckConstraint(
                check=models.Q(payment_period_end__gte=models.F("payment_period_start")),
                name="valid_salary_period"
            ),
        ]

    def __str__(self):
        return (
            f"{self.receiver.get_full_name()} | "
            f"{self.amount} | "
            f"{self.payment_period_start} → {self.payment_period_end}"
        )

    # -----------------------
    # Business logic
    # -----------------------

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_transaction_id():
        import uuid
        ts = timezone.now().strftime("%Y%m%d%H%M%S")
        return f"SAL-{ts}-{uuid.uuid4().hex[:8].upper()}"

    def mark_as_processing(self):
        self.status = "PROCESSING"
        self.save(update_fields=["status", "updated_at"])

    def mark_as_paid(self, payment_reference=None):
        self.status = "SUCCESS"
        self.processed_at = timezone.now()
        if payment_reference:
            self.payment_reference = payment_reference
        self.save()

    def mark_as_failed(self, reason=None):
        self.status = "FAILED"
        if reason:
            self.note = reason
        self.save()

    def is_pending(self):
        return self.status == "PENDING"

    def is_successful(self):
        return self.status == "SUCCESS"
