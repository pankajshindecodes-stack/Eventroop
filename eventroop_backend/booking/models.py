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


class Location(models.Model):
    LOCATION_TYPE_CHOICES = [
        ("OPD", "OPD"),
        ("PARTNER", "Partner"),
        ("CLIENT", "Client"),
    ]
    
    user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_location",
    )
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES)
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

class BookingTypeChoices(models.TextChoices):
        IN_HOUSE = 'IN_HOUSE', 'In House'
        OPD = 'OPD', 'OPD'
        CLIENT_SIDE = 'CLIENT_SIDE', 'Client Side'
    
class PeriodChoices(models.TextChoices):
    HOURLY = "HOURLY", "Hourly"
    DAILY = "DAILY", "Daily"
    MONTHLY = "MONTHLY", "Monthly"

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
        choices=BookingTypeChoices.choices,
        default=BookingTypeChoices.IN_HOUSE
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


class InvoiceBookingStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    BOOKED = 'BOOKED', 'Booked'
    DELAYED = 'DELAYED', 'Delayed'
    CANCELLED = 'CANCELLED', 'Cancelled'
    FULFILLED = 'FULFILLED', 'Fulfilled'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    YET_TO_BE_STARTED = 'YET_TO_BE_STARTED', 'Yet To Be Started'
    PARTIALLY_FULFILLED = 'PARTIALLY_FULFILLED', 'Partially Fulfilled'

class InvoiceBooking(models.Model):  
    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        db_index=True  # Better query performance for user lookups
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        db_index=True
    )
    venue = models.ForeignKey(
        "venue_manager.Venue",
        on_delete=models.SET_NULL,
        null=True,
        db_index=True
    )
    venue_package = models.ForeignKey(
        "Package",  # Use string reference for clarity
        on_delete=models.CASCADE,
        related_name="invoice_bookings",
        limit_choices_to={'content_type__model': 'venue'},
    )

    start_datetime = models.DateTimeField(db_index=True)  # Index for date range queries
    end_datetime = models.DateTimeField(db_index=True)

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),  # Use Decimal instead of int
        editable=False  # Computed field, prevent manual editing
    )

    booking_type = models.CharField(
        max_length=25,
        choices=BookingTypeChoices.choices,
        default=BookingTypeChoices.IN_HOUSE,
        db_index=True  # Frequently filtered
    )
    status = models.CharField(
        max_length=25,
        choices=InvoiceBookingStatus.choices,
        default=InvoiceBookingStatus.DRAFT,
        db_index=True  # Frequently filtered
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)  # Track updates

    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['patient', 'created_at']),
            models.Index(fields=['start_datetime', 'end_datetime']),
        ]

    def __str__(self):
        return f"Booking #{self.id}-{self.venue.name}"

    @property
    def is_ongoing(self):
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime
    
    @property
    def is_upcoming(self):
        return self.start_datetime > timezone.now()
    
    @property
    def is_past_order(self):
        return self.end_datetime < timezone.now()
    
    def save(self, *args, **kwargs):
        self.subtotal = self._calculate_subtotal()
        super().save(*args, **kwargs)
    
    def _calculate_subtotal(self):
        """Calculate subtotal using package cost function"""
        from .utils import calculate_package_cost  # Import at function level to avoid circular imports
        return calculate_package_cost(
            self.venue_package,
            self.start_datetime,
            self.end_datetime
        )
    
    def cancel(self):
        """
        Cancel this booking and all related services.
        """

        if self.status == InvoiceBookingStatus.CANCELLED:
            return  # already cancelled

        if self.status == InvoiceBookingStatus.FULFILLED:
            raise ValidationError("Fulfilled bookings cannot be cancelled.")

        with transaction.atomic():

            # Cancel main booking
            self.status = InvoiceBookingStatus.CANCELLED
            self.updated_at = timezone.now()

            # Optional: reset subtotal
            self.subtotal = 0

            self.save(update_fields=["status", "updated_at", "subtotal"])

            # Cancel all related services
            self.services.update(
                status=InvoiceBookingStatus.CANCELLED,
                updated_at=timezone.now(),
                subtotal=0
            )

class InvoiceBookingService(models.Model): 
    booking = models.ForeignKey(
        InvoiceBooking,
        null=True,
        blank=True,
        related_name="services",  # Better naming
        on_delete=models.CASCADE,
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

    service = models.ForeignKey(
        "venue_manager.Service",
        on_delete=models.CASCADE,
        db_index=True
    )
    
    service_package = models.ForeignKey(
        "Package",
        on_delete=models.CASCADE,
        related_name="service_bookings",
        limit_choices_to={'content_type__model': 'service'},
    )

    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField(db_index=True)

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False
    )

    status = models.CharField(
        max_length=25,
        choices=InvoiceBookingStatus.choices,
        default=InvoiceBookingStatus.DRAFT,
        db_index=True
    )
    booking_type = models.CharField(
        max_length=25,
        choices=BookingTypeChoices.choices,
        default=BookingTypeChoices.OPD,
        db_index=True  # Frequently filtered
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['service', 'created_at']),
            models.Index(fields=['start_datetime', 'end_datetime']),
        ]

    def __str__(self):
        booking_instance = self.booking if self.booking else "Standalone"
        return f"P-{self.patient.id}|{booking_instance}|{self.service.name}|{self.status}"
    
    @property
    def is_ongoing(self):
        now = timezone.now()
        return self.start_datetime <= now <= self.end_datetime
    
    @property
    def is_upcoming(self):  # Fixed typo
        return self.start_datetime > timezone.now()
    
    @property
    def is_past_order(self):
        return self.end_datetime < timezone.now()
    
    def save(self, *args, **kwargs):        
        self.subtotal = self._calculate_subtotal()
        super().save(*args, **kwargs)
    
    def _calculate_subtotal(self):
        """Calculate subtotal using package cost function"""
        from .utils import calculate_package_cost
        print(self.start_datetime,type(self.start_datetime))
        print(self.end_datetime)        
        return calculate_package_cost(
            self.service_package,
            self.start_datetime,
            self.end_datetime
        )
    def cancel(self):
        """
        Cancel only this service booking.
        """

        if self.status == InvoiceBookingStatus.CANCELLED:
            return

        if self.status == InvoiceBookingStatus.FULFILLED:
            raise ValidationError("Fulfilled services cannot be cancelled.")

        with transaction.atomic():

            self.status = InvoiceBookingStatus.CANCELLED
            self.updated_at = timezone.now()

            # Optional business rule
            self.subtotal = Decimal('0.0')
            

            self.save(update_fields=["status", "updated_at", "subtotal"])
   

class InvoiceStatus(models.TextChoices):
    UNPAID = 'UNPAID', 'Unpaid'
    PARTIALLY_PAID = 'PARTIALLY_PAID', 'Partially Paid'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'
    REFUNDED = 'REFUNDED', 'Refunded'

class PaymentMethod(models.TextChoices):
    CASH = 'CASH', 'Cash'
    UPI = 'UPI', 'UPI'
    CARD = 'CARD', 'Card'
    BANK = 'BANK', 'Bank'
    CHEQUE = 'CHEQUE', 'Cheque'

class TotalInvoice(models.Model):
    booking = models.OneToOneField(
        'InvoiceBooking',
        related_name="invoice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True
    )

    service_bookings = models.ManyToManyField(
        'InvoiceBookingService',
        blank=True,
        related_name="invoices"
    )

    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        db_index=True
    )

    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        db_index=True
    )

    # Financial Fields
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Discount & Tax (NEW)
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Status & Dates
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.UNPAID,
        db_index=True
    )

    due_date = models.DateField(null=True, blank=True, db_index=True)
    issued_date = models.DateField(auto_now_add=True, db_index=True)
    paid_date = models.DateField(null=True, blank=True, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def generate_invoice_number():
        return f"INV-FNF-{uuid.uuid4().hex[:10].upper()}"
    
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique invoice identifier",
        default=generate_invoice_number
    )

    notes = models.TextField(
        blank=True,
        help_text="Additional notes or payment terms"
    )

    
    class Meta:
        ordering = ['-issued_date']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        indexes = [
            models.Index(fields=['patient', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['issued_date', 'status']),
            models.Index(fields=['patient', 'issued_date']),
        ]
    
    def __str__(self):
        return f"{self.invoice_number}"

    def clean(self):
        """Validation on save"""
        if self.paid_amount > self.total_amount:
            raise ValidationError("Paid amount cannot exceed total amount")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def recalculate_totals(self):
        """Recalculate invoice total from booking and services"""
        booking_total = self.booking.subtotal if self.booking else Decimal('0.00')

        services_total = (
            self.service_bookings.aggregate(
                total=Coalesce(
                    Sum('subtotal'),
                    Decimal('0.00'),
                    output_field=DecimalField()
                )
            )['total'] or Decimal('0.00')
        )

        # Calculate total with tax and discount
        subtotal = booking_total + services_total
        self.total_amount = subtotal + self.tax_amount - self.discount_amount

        # Ensure total never goes below 0
        self.total_amount = max(self.total_amount, Decimal('0.00'))

        self.recalculate_remaining()
        self.save(update_fields=[
            'total_amount',
            'remaining_amount',
            'updated_at'
        ])

    def recalculate_remaining(self):
        """Recalculate remaining amount"""
        self.remaining_amount = max(
            self.total_amount - self.paid_amount,
            Decimal('0.00')
        )

    def recalculate_payments(self):
        """Recalculate payment status and amounts"""
        if not self.pk:
            return

        # Aggregate payments from related Payment objects
        paid = (
            self.payments.aggregate(
                total=Coalesce(
                    Sum('amount'),
                    Decimal('0.00'),
                    output_field=DecimalField()
                )
            )['total'] or Decimal('0.00')
        )

        self.paid_amount = paid
        self.recalculate_remaining()

        # Update status
        self._update_status()

        # Set paid date if fully paid
        if self.status == InvoiceStatus.PAID and not self.paid_date:
            self.paid_date = timezone.now().date()
        elif self.status != InvoiceStatus.PAID:
            self.paid_date = None

        self.save(update_fields=[
            'paid_amount',
            'remaining_amount',
            'status',
            'paid_date',
            'updated_at'
        ])

    def _update_status(self):
        """Update invoice status based on payment and due date"""
        if self.status == InvoiceStatus.CANCELLED or self.status == InvoiceStatus.REFUNDED:
            return  # Don't change cancelled/refunded invoices

        # Determine payment status
        if self.paid_amount <= 0:
            new_status = InvoiceStatus.UNPAID
        elif self.paid_amount >= self.total_amount:
            new_status = InvoiceStatus.PAID
        else:
            new_status = InvoiceStatus.PARTIALLY_PAID

        # Check if overdue
        is_overdue = (
            self.due_date and
            timezone.now().date() > self.due_date and
            new_status != InvoiceStatus.PAID
        )

        self.status = InvoiceStatus.OVERDUE if is_overdue else new_status

    def is_overdue(self):
        """Check if invoice is overdue"""
        return (
            self.due_date and
            timezone.now().date() > self.due_date and
            self.status != InvoiceStatus.PAID
        )

    def is_fully_paid(self):
        """Check if invoice is fully paid"""
        return self.status == InvoiceStatus.PAID

    def days_overdue(self):
        """Get number of days overdue"""
        if not self.is_overdue():
            return 0
        return (timezone.now().date() - self.due_date).days

    @classmethod
    def get_overdue_invoices(cls):
        """Get all overdue invoices"""
        today = timezone.now().date()
        return cls.objects.filter(
            Q(status__in=[InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID]),
            due_date__lt=today
        )

    @classmethod
    def get_pending_invoices(cls, patient=None):
        """Get unpaid invoices, optionally filtered by patient"""
        qs = cls.objects.filter(status=InvoiceStatus.UNPAID)
        if patient:
            qs = qs.filter(patient=patient)
        return qs

    @classmethod
    def get_patient_total_outstanding(cls, patient):
        """Get total outstanding amount for a patient"""
        return cls.objects.filter(
            patient=patient,
            status__in=[InvoiceStatus.UNPAID, InvoiceStatus.PARTIALLY_PAID]
        ).aggregate(
            total=Coalesce(
                Sum('remaining_amount'),
                Decimal('0.00'),
                output_field=DecimalField()
            )
        )['total']

    @classmethod
    def get_revenue_summary(cls, start_date=None, end_date=None):
        """Get revenue summary for date range"""
        qs = cls.objects.filter(status=InvoiceStatus.PAID)
        if start_date:
            qs = qs.filter(paid_date__gte=start_date)
        if end_date:
            qs = qs.filter(paid_date__lte=end_date)
        
        return qs.aggregate(
            total_revenue=Coalesce(
                Sum('total_amount'),
                Decimal('0.00'),
                output_field=DecimalField()
            ),
            count=models.Count('id')
        )

class Payment(models.Model):
    # Relations
    invoice = models.ForeignKey(
        TotalInvoice,
        related_name="payments",
        on_delete=models.CASCADE,
        db_index=True
    )

    patient = models.ForeignKey(
        'Patient',
        on_delete=models.CASCADE,
        db_index=True,
        editable=False
    )

    # Payment Details
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        db_index=True
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Transaction ID, check number, UTR, etc."
    )

    # Payment Status (NEW)
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether payment has been verified"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        indexes = [
            models.Index(fields=['invoice', 'created_at']),
            models.Index(fields=['patient', 'method']),
            models.Index(fields=['created_at', 'method']),
            models.Index(fields=['is_verified', 'created_at']),
        ]

    def __str__(self):
        return f"{self.amount} - {self.get_method_display()} ({self.created_at.date()})"

    def clean(self):
        """Validate payment amount"""
        if self.amount <= 0:
            raise ValidationError("Payment amount must be greater than 0")
        

    def save(self, *args, **kwargs):
        self.full_clean()
        
        # Auto-assign patient from invoice
        if self.invoice and not self.patient_id:
            self.patient = self.invoice.patient
        
        # Auto-generate reference if not provided
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:12].upper()}"
        is_new = self.pk is None

        super().save(*args, **kwargs)

        # Recalculate invoice totals after payment is saved
        if is_new:
            self.invoice.recalculate_payments()

    def delete(self, *args, **kwargs):
        """Recalculate invoice when payment is deleted"""
        invoice = self.invoice
        super().delete(*args, **kwargs)
        if invoice:
            invoice.recalculate_payments()

    @classmethod
    def get_unverified_payments(cls):
        """Get all unverified payments"""
        return cls.objects.filter(is_verified=False)

    @classmethod
    def get_payments_by_method(cls, method):
        """Get payments filtered by method"""
        return cls.objects.filter(method=method)

