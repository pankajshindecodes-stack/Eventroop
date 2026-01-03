from django.db import models
from accounts.models import CustomUser
from django.utils import timezone
from django.db.models import Q, F


class SalaryStructure(models.Model):

    SALARY_TYPE_CHOICES = [
        ("HOURLY", "Hourly"),
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("FORTNIGHTLY", "Fortnightly"),
        ("MONTHLY", "Monthly"),
    ]

    SALARY_CHANGE_TYPE = [
        ("BASE_SALARY", "Base Salary"),
        ("INCREMENT", "Increment"),
        ("ADVANCE", "Advance"),
        ("LOAN", "Loan"),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="salary_structures"
    )

    salary_type = models.CharField(
        max_length=20,
        choices=SALARY_TYPE_CHOICES,
        default="MONTHLY"
    )

    change_type = models.CharField(
        max_length=20,
        choices=SALARY_CHANGE_TYPE,
        default="BASE_SALARY"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    final_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    effective_from = models.DateField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from"]
        unique_together = ("user", "effective_from")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(change_type="BASE_SALARY"),
                name="unique_base_salary_per_user"
            )
        ]

    def save(self, *args, **kwargs):
        """
        Salary calculation rules:
        - BASE_SALARY → sets final_salary
        - INCREMENT → final_salary = latest final_salary + increment
        """
        self.full_clean()
        # Fetch last salary record before this effective date (excluding current record)
        previous = (
            SalaryStructure.objects
            .filter(user=self.user, effective_from__lte=self.effective_from)
            .exclude(pk=self.pk)  # Exclude current record
            .order_by("-effective_from")
            .first()
        )

        previous_salary = previous.final_salary if previous else 0

        if self.change_type == "BASE_SALARY":
            self.final_salary = self.amount

        elif self.change_type == "INCREMENT":
            self.final_salary = previous_salary + self.amount

        elif self.change_type in ["ADVANCE", "LOAN"]:
            # Salary unchanged, deductions handled elsewhere if needed
            self.final_salary = previous_salary

        super().save(*args, **kwargs)

class SalaryTransaction(models.Model):
    """
    Payroll / Salary payment transaction
    """

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

    transaction_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER", "VSRE_STAFF"]},
        related_name="salary_receiver"
    )

    # Payment amounts
    total_payable_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    remaining_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    payment_period_start = models.DateField()
    payment_period_end = models.DateField()

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default="CASH"
    )

    payment_reference = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
        db_index=True
    )

    note = models.TextField(blank=True, null=True)

    processed_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_period_start"]
        indexes = [
            models.Index(fields=["user", "-processed_at"]),
            models.Index(fields=["status", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(total_payable_amount__gt=0),
                name="total_payable_amount_positive"
            ),
            models.CheckConstraint(
                check=Q(payment_period_end__gte=F("payment_period_start")),
                name="valid_salary_period"
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.get_full_name()} | "
            f"Payable: {self.total_payable_amount} | Paid: {self.paid_amount}"
        )

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()

        self.remaining_payment = max(
            self.total_payable_amount - self.paid_amount, 0
        )

        super().save(*args, **kwargs)

    @staticmethod
    def generate_transaction_id():
        import uuid
        ts = timezone.now().strftime("%Y%m%d%H%M%S")
        return f"P-{ts}-{uuid.uuid4().hex[:8].upper()}"

    # Status helpers
    def mark_as_processing(self):
        self.status = "PROCESSING"
        self.save(update_fields=["status", "updated_at"])

    def mark_as_paid(self, paid_amount=None, payment_reference=None):
        self.status = "SUCCESS"
        self.processed_at = timezone.now()
        self.paid_amount = paid_amount or self.total_payable_amount
        if payment_reference:
            self.payment_reference = payment_reference
        self.save()

    def mark_as_failed(self, reason=None):
        self.status = "FAILED"
        if reason:
            self.note = reason
        self.save()

    def is_fully_paid(self):
        return self.remaining_payment == 0 and self.status == "SUCCESS"
