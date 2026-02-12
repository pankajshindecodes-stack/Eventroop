from django.db import models,transaction
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import CustomUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from django.db.models import Sum, F, Q, DecimalField
from django.db.models.functions import Coalesce
from decimal import Decimal
import re
import uuid
from .constants import *

class Location(models.Model):
        
    user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_location",
    )
    location_type = models.CharField(max_length=20, choices=BookingType.choices)
    building_name = models.CharField(max_length=250)
    address_line1 = models.CharField(max_length=250)
    address_line2 = models.CharField(max_length=250, blank=True, null=True)
    locality = models.CharField(max_length=250)
    city = models.CharField(max_length=250)
    state = models.CharField(max_length=250)
    postal_code = models.CharField(max_length=20)

    
    class Meta:
        verbose_name = "Location"
        verbose_name_plural = "Locations"
        indexes = [
            models.Index(fields=['location_type']),
            models.Index(fields=['city', 'state']),
        ]

    def __str__(self):
        return f"{self.building_name} ({self.city})"

    def full_address(self):
        """Return formatted full address"""
        parts = [
            self.building_name,
            self.address_line1,
            self.address_line2,
            self.locality,
            self.city,
            self.state,
            self.postal_code,
        ]
        return ", ".join(filter(None, parts))

class Package(models.Model):   
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='packages',
        limit_choices_to={"user_type": "VSRE_OWNER"}
    )

    # Polymorphic relation: belongs_to → Venue | Service | Resource
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        limit_choices_to={
            'model__in': [
                'venue','service','resource'
            ]
        }
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    belongs_to = GenericForeignKey('content_type', 'object_id')

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    package_type = models.CharField(
        max_length=20,
        choices=BookingType.choices,
        default=BookingType.IN_HOUSE
    )
    period = models.CharField(
        max_length=10,
        choices=PeriodChoices.choices,
        default=PeriodChoices.MONTHLY
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        verbose_name = "Package"
        verbose_name_plural = "Packages"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['package_type', 'is_active']),
            models.Index(fields=['owner', '-created_at']),
        ]

    def __str__(self):
        return f"{self.name} ({self.package_type})"

class Patient(models.Model):
    """Model for storing patient registration and medical information"""
    
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer-not-to-say', 'Prefer not to say'),
    ]
    
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'),
        ('A-', 'A-'),
        ('B+', 'B+'),
        ('B-', 'B-'),
        ('AB+', 'AB+'),
        ('AB-', 'AB-'),
        ('O+', 'O+'),
        ('O-', 'O-'),
    ]
    
    ID_PROOF_CHOICES = [
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('passport', 'Passport'),
        ('driving-license', 'Driving License'),
        ('voter-id', 'Voter ID'),
        ('other', 'Other'),
    ]
    
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('credit-card', 'Credit Card'),
        ('debit-card', 'Debit Card'),
        ('net-banking', 'Net Banking'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('bank-transfer', 'Bank Transfer'),
    ]
    
    # Validators
    phone_regex = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be 10 digits"
    )
    
    registered_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='registered_patients',
        help_text="User who registered this patient"
    )

    # Basic Information
    patient_id = models.CharField(max_length=20, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    
    # Contact Information
    phone = models.CharField(max_length=10, validators=[phone_regex])
    address = models.TextField()
    age = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    
    # Emergency Contacts
    emergency_contact = models.CharField(max_length=100)
    emergency_phone = models.CharField(max_length=10, validators=[phone_regex])
    emergency_contact_2 = models.CharField(max_length=100, null=True, blank=True)
    emergency_phone_2 = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        validators=[phone_regex]
    )
    
    # Medical Information
    medical_conditions = models.TextField(null=True, blank=True)
    allergies = models.TextField(null=True, blank=True)
    present_health_condition = models.TextField(null=True, blank=True)
    
    # Personal Details
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES, null=True, blank=True)
    preferred_language = models.CharField(max_length=20, null=True, blank=True)
    
    # Identification
    id_proof = models.CharField(max_length=20, choices=ID_PROOF_CHOICES)
    id_proof_number = models.CharField(max_length=50)
    patient_documents = models.FileField(upload_to='patient_documents/')
    
    # Professional Background
    education_qualifications = models.TextField(null=True, blank=True)
    earlier_occupation = models.CharField(max_length=200, null=True, blank=True)
    year_of_retirement = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1950), MaxValueValidator(timezone.localtime().year)]
    )
    
    # Payment Information
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=5000.00)
    advance_payment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100000)]
    )
    payment_mode = models.CharField(
        max_length=20,
        choices=PAYMENT_MODE_CHOICES,
        null=True,
        blank=True
    )
    registration_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = 'Patients'
        ordering = ['-registration_date']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['-registration_date']),
            models.Index(fields=['registered_by']),
            models.Index(fields=['first_name', 'last_name']),
        ]
    
    def __str__(self):
        email_display = self.email if self.email else "No Email"
        return f"{self.get_full_name()} - {email_display}"
    
    def get_full_name(self):
        """Return patient's full name"""
        return f"{self.first_name} {self.last_name}"
      
    def get_total_payment(self):
        """Return total payment (registration fee + advance payment)"""
        total = self.registration_fee
        if self.advance_payment:
            total += self.advance_payment
        return total
    
    def clean(self):
        """Custom validation"""
        self._validate_id_proof()
        self._validate_payment()
    
    def _validate_id_proof(self):
        """Validate ID proof number based on type"""
        if self.id_proof == 'aadhar' and self.id_proof_number:
            if not self.id_proof_number.isdigit() or len(self.id_proof_number) != 12:
                raise ValidationError('Aadhar number must be 12 digits')
        
        if self.id_proof == 'pan' and self.id_proof_number:
            if len(self.id_proof_number) != 10:
                raise ValidationError('PAN number must be 10 characters')
            # PAN format: 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F)
            pan_pattern = r'^[A-Z]{5}\d{4}[A-Z]{1}$'
            if not re.match(pan_pattern, self.id_proof_number.upper()):
                raise ValidationError('PAN number must be in format: ABCDE1234F (5 letters, 4 digits, 1 letter)')
    
    def _validate_payment(self):
        """Validate payment details"""
        if self.advance_payment and self.advance_payment > 0 and not self.payment_mode:
            raise ValidationError('Payment mode is required when advance payment is provided')
    
    def save(self, *args, **kwargs):
        self.full_clean()        
        super().save(*args, **kwargs)

class InvoiceBooking(models.Model):

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
        db_index=True
    )

    booking_entity = models.CharField(
        max_length=20,
        choices=BookingEntity.choices,
        default=BookingEntity.VENUE,
        db_index=True
    )

    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        db_index=True
    )

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        db_index=True
    )

    venue = models.ForeignKey(
        "venue_manager.Venue",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True
    )

    service = models.ForeignKey(
        "venue_manager.Service",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_index=True
    )

    package = models.ForeignKey(
        "Package",
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField(db_index=True)

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    premium_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False
    )

    booking_type = models.CharField(
        max_length=25,
        choices=BookingType.choices,
        default=BookingType.OPD,
        db_index=True
    )

    status = models.CharField(
        max_length=25,
        choices=BookingStatus.choices,
        default=BookingStatus.DRAFT,
        db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        if self.booking_entity == BookingEntity.SERVICE:
            entity = self.service
        elif self.booking_entity == BookingEntity.VENUE:
            entity = self.venue
        else:
            entity = None
        
        return (
            f"#{self.pk} | "
            f"{self.booking_entity.capitalize()} | "
            f"{self.patient.get_full_name()} | "
            f"{entity}"
        )

    
    def clean(self):
        if self.booking_entity == "VENUE" and not self.venue:
            raise ValidationError("Venue booking requires venue.")

        if self.booking_entity == "SERVICE" and not self.service:
            raise ValidationError("Service booking requires service.")

    def save(self, *args, **kwargs):
        self.full_clean()
        subtotal = self._calculate_subtotal()
        self.subtotal = (subtotal - self.discount_amount) + self.premium_amount
        super().save(*args, **kwargs)

    def _calculate_subtotal(self):
        from .utils import calculate_package_cost
        return calculate_package_cost(
            self.package,
            self.start_datetime,
            self.end_datetime
        )

    def cancel(self):

        if self.status == BookingStatus.CANCELLED:
            return

        with transaction.atomic():

            self.status = BookingStatus.CANCELLED
            self.subtotal = Decimal("0")
            self.save(update_fields=["status", "subtotal"])

            self.children.update(
                status=BookingStatus.CANCELLED,
                subtotal=0
            )

class TotalInvoice(models.Model):

    booking = models.ForeignKey(
        InvoiceBooking,
        related_name="invoices",
        on_delete=models.CASCADE
    )

    period_start = models.DateTimeField(db_index=True)
    period_end = models.DateTimeField(db_index=True)

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    user = models.ForeignKey("accounts.CustomUser", on_delete=models.CASCADE)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.UNPAID
    )

    due_date = models.DateField(null=True, blank=True)
    issued_date = models.DateField(auto_now_add=True)
    paid_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def generate_invoice_number():
        return f"INV-{uuid.uuid4().hex[:10].upper()}"
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        default=generate_invoice_number
    )

    # -------------------------------------------------

    def recalculate_totals(self):
        from .utils import calculate_package_cost
        from django.db.models import Sum
        from django.db.models.functions import Coalesce

        # Venue portion (monthly slice)
        venue_amount = calculate_package_cost(
            self.booking.package,
            self.period_start,
            self.period_end
        )

        # Services in this period
        services_total = (
            self.booking.children.filter(
                start_datetime__lt=self.period_end,
                end_datetime__gt=self.period_start
            ).aggregate(
                total=Coalesce(Sum("subtotal"), Decimal("0"))
            )["total"]
        )

        subtotal = venue_amount + services_total

        self.total_amount = subtotal + self.tax_amount
        self.remaining_amount = self.total_amount - self.paid_amount

        self.save()

    def recalculate_payments(self):

        paid = self.payments.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0"))
        )["total"]

        self.paid_amount = paid
        self.remaining_amount = max(self.total_amount - paid, Decimal("0"))

        if paid == 0:
            self.status = InvoiceStatus.UNPAID
        elif paid >= self.total_amount:
            self.status = InvoiceStatus.PAID
            self.paid_date = timezone.now().date()
        else:
            self.status = InvoiceStatus.PARTIALLY_PAID

        self.save()

class Payment(models.Model):

    invoice = models.ForeignKey(
        TotalInvoice,
        related_name="payments",
        on_delete=models.CASCADE
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)

    reference = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:10].upper()}"

        super().save(*args, **kwargs)

        self.invoice.recalculate_payments()
