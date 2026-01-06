from django.db import models
from accounts.models import CustomUser
from django.utils import timezone
from django.db.models import Q, F
from decimal import Decimal
from django.core.validators import MinValueValidator



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
                fields=["user", "effective_from"],
                condition=models.Q(change_type="BASE_SALARY"),
                name="unique_base_salary_per_user_per_date"
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
            .filter(
                user=self.user,
                effective_from__lte=self.effective_from,
                change_type__in=["BASE_SALARY","INCREMENT"]
            )
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
        
class SalaryReport(models.Model):
    """
    Salary calculation & payment breakdown report.
    Acts as an immutable audit record per salary period.
    """

    # -------------------- Relations --------------------
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="salary_reports",
        limit_choices_to={
            "user_type__in": [
                "VSRE_MANAGER",
                "LINE_MANAGER",
                "VSRE_STAFF",
            ]
        },
    )

    # -------------------- Period --------------------
    start_date = models.DateField()
    end_date = models.DateField()

    # -------------------- Salary Structure --------------------
    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    total_payable_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    remaining_payment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )

    # -------------------- Audit --------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -------------------- Computed --------------------
    @property
    def final_salary(self):
        """
        Fetch applicable salary structure for the report period.
        """
        salary = (
            SalaryStructure.objects
            .filter(
                user=self.user,
                effective_from__lte=self.end_date,
                change_type__in=["BASE_SALARY","INCREMENT"]
            )
            .order_by("-effective_from")
            .first()
        )
        return salary.final_salary if salary else Decimal("0.00")
    
    @property
    def advance_amount(self):
        """
        Fetch applicable salary structure for the report period.
        """

        salary = (
            SalaryStructure.objects
            .filter(
                user=self.user,
                effective_from__lte=self.end_date,
                change_type__in=["ADVANCE","LOAN"]
            )
            .order_by("-effective_from")
            .first()
        )
        return salary.amount if salary else Decimal("0.00")

    # -------------------- Overrides --------------------
    def save(self, *args, **kwargs):
        """
        Auto-calculate remaining payment and adjust advance if needed.
        """
        self.remaining_payment = self.total_payable_amount - self.paid_amount        
        super().save(*args, **kwargs)
    # -------------------- Meta --------------------
    class Meta:
        ordering = ["-start_date"]
        unique_together = ("user", "start_date", "end_date")
        verbose_name = "Salary Report"
        verbose_name_plural = "Salary Reports"
        

    def __str__(self):
        return f"{self.user} | {self.start_date} → {self.end_date}"
    
# class SalaryTransaction(models.Model):
#     """
#     Payroll / Salary payment transaction
#     Records actual payment against an approved salary report
#     """

#     PAYMENT_METHOD_CHOICES = [
#         ("BANK_TRANSFER", "Bank Transfer"),
#         ("CHECK", "Check"),
#         ("CASH", "Cash"),
#         ("UPI", "UPI"),
#         ("OTHER", "Other"),
#     ]

#     STATUS_CHOICES = [
#         ("PENDING", "Pending"),
#         ("PROCESSING", "Processing"),
#         ("SUCCESS", "Success"),
#         ("FAILED", "Failed"),
#         ("CANCELLED", "Cancelled"),
#     ]

#     transaction_id = models.CharField(
#         max_length=50,
#         unique=True,
#         null=True,
#         db_index=True
#     )

#     # Link to salary report (source of truth for calculations)
#     salary_report = models.OneToOneField(
#         SalaryReport,
#         on_delete=models.PROTECT,
#         related_name="transaction",
#         help_text="Reference to the approved salary report"
#     )

#     # Payment amounts
#     amount_to_pay = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         help_text="Amount to be paid (from salary_report.net_payable)"
#     )

#     amount_paid = models.DecimalField(
#         max_digits=12,
#         decimal_places=2,
#         default=0,
#         help_text="Actual amount paid"
#     )

#     payment_method = models.CharField(
#         max_length=20,
#         choices=PAYMENT_METHOD_CHOICES,
#         default="CASH"
#     )

#     payment_reference = models.CharField(
#         max_length=100,
#         blank=True,
#         null=True,
#         unique=True,
#         help_text="Bank reference, check number, UPI transaction ID, etc."
#     )

#     status = models.CharField(
#         max_length=20,
#         choices=STATUS_CHOICES,
#         default="PENDING",
#         db_index=True
#     )

#     note = models.TextField(blank=True, null=True)

#     processed_at = models.DateTimeField(blank=True, null=True)

#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         ordering = ["-created_at"]
#         indexes = [
#             models.Index(fields=["salary_report__user", "-processed_at"]),
#             models.Index(fields=["status", "created_at"]),
#         ]
#         constraints = [
#             models.CheckConstraint(
#                 check=Q(amount_to_pay__gt=0),
#                 name="amount_to_pay_positive"
#             ),
#         ]

#     def __str__(self):
#         return (
#             f"{self.salary_report.user.get_full_name()} | "
#             f"Transaction: {self.transaction_id} | Amount: {self.amount_paid}"
#         )

#     def save(self, *args, **kwargs):
#         FINAL_STATUSES = {"SUCCESS", "FAILED", "CANCELLED"}

#         # Generate transaction ID only for final statuses
#         if not self.transaction_id and self.status in FINAL_STATUSES:
#             self.transaction_id = self.generate_transaction_id()

#         super().save(*args, **kwargs)

#     @staticmethod
#     def generate_transaction_id():
#         import uuid
#         return f"SAL{uuid.uuid4().hex[:12].upper()}"

#     # Status helpers
#     def mark_as_processing(self):
#         """Mark transaction as processing"""
#         self.status = "PROCESSING"
#         self.save(update_fields=["status", "updated_at"])

#     def mark_as_paid(self, paid_amount=None, payment_reference=None):
#         """Mark transaction as successfully paid"""
#         self.status = "SUCCESS"
#         self.processed_at = timezone.now()
#         self.amount_paid = paid_amount or self.amount_to_pay
#         if payment_reference:
#             self.payment_reference = payment_reference
#         self.save()

#     def mark_as_failed(self, reason=None):
#         """Mark transaction as failed"""
#         self.status = "FAILED"
#         if reason:
#             self.note = reason
#         self.save()

#     def mark_as_cancelled(self, reason=None):
#         """Mark transaction as cancelled"""
#         self.status = "CANCELLED"
#         if reason:
#             self.note = reason
#         self.save()

#     def is_fully_paid(self):
#         """Check if transaction is fully paid"""
#         return (
#             self.amount_paid == self.amount_to_pay and
#             self.status == "SUCCESS"
#         )