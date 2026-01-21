from django.db import models,transaction as db_manager
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import CustomUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal


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
        verbose_name_plural = "Locations"

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
    class PackageTypeChoices(models.TextChoices):
        IN_HOUSE = 'IN_HOUSE', 'In House'
        OPD = 'OPD', 'OPD'
        CLIENT_SIDE = 'CLIENT_SIDE', 'Client Side'
    
    class PeriodChoices(models.TextChoices):
        HOURLY = "HOURLY", "Hourly"
        DAILY = "DAILY", "Daily"
        MONTHLY = "MONTHLY", "Monthly"
    
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='packages',
        limit_choices_to={"user_type": "VSRE_OWNER"}
    )

    # Polymorphic relation: belongs_to → Venue | Service | Resource
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    belongs_to = GenericForeignKey('content_type', 'object_id')

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    package_type = models.CharField(
        max_length=20,
        choices=PackageTypeChoices.choices,
        default=PackageTypeChoices.IN_HOUSE
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
        ordering = ['-created_at']

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
        ordering = ['-registration_date']
        verbose_name_plural = 'Patients'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['-registration_date']),
            models.Index(fields=['registered_by']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} - {self.email}"
    
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
    
    def _validate_payment(self):
        """Validate payment details"""
        if self.advance_payment and self.advance_payment > 0 and not self.payment_mode:
            raise ValidationError('Payment mode is required when advance payment is provided')
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class BookingStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    BOOKED = "BOOKED", "Booked"
    DELAYED = "DELAYED", "Delayed"
    CANCELLED = "CANCELLED", "Cancelled"
    FULFILLED = "FULFILLED", "Fulfilled"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    YET_TO_BE_STARTED = "YET_TO_BE_STARTED", "Yet To Be Started"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED", "Partially Fulfilled"

class Booking(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="bookings_created")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="bookings")

    venue = models.ForeignKey(
        "venue_manager.Venue",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="bookings"
    )

    venue_package = models.ForeignKey(
        Package,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="venue_bookings",
        limit_choices_to={"content_type__model": "venue"},
    )

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    venue_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    services_cost = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    final_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    status = models.CharField(max_length=25, choices=BookingStatus.choices, default=BookingStatus.DRAFT)
    continue_booking = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["patient", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["venue", "start_datetime"]),
        ]

    # ---------------- VALIDATION ---------------- #

    def clean(self):
        if self.discount < 0:
            raise ValidationError("Discount cannot be negative.")

    # ---------------- COST LOGIC ---------------- #

    def recalculate_totals(self):
        self.venue_cost = self._calculate_venue_cost()
        self.services_cost = self._calculate_services_cost()
        self.subtotal = self.venue_cost + self.services_cost
        self.final_amount = max(Decimal("0.00"), self.subtotal - self.discount)

    def _calculate_venue_cost(self):
        if not (self.venue and self.venue_package):
            return Decimal("0.00")
        return self._calculate_package_cost(
            self.venue_package, self.start_datetime, self.end_datetime
        )

    def _calculate_services_cost(self):
        if not self.pk:
            return Decimal("0.00")
        return sum(
            (service.calculate_cost() for service in self.booking_services.all()),
            Decimal("0.00")
        )

    @staticmethod
    def _calculate_package_cost(package, start_dt, end_dt):
        duration = end_dt - start_dt

        if package.period == Package.PeriodChoices.HOURLY:
            hours = Decimal(duration.total_seconds()) / Decimal("3600")
            total_cal = hours.quantize(Decimal("0.01")) * package.price
            return round(total_cal,2)

        if package.period == Package.PeriodChoices.DAILY:
            days = max(1, duration.days + (1 if duration.seconds else 0))
            return Decimal(days) * package.price

        if package.period == Package.PeriodChoices.MONTHLY:
            months = Booking._months_between(start_dt, end_dt)
            return Decimal(months) * package.price

        return Decimal("0.00")

    @staticmethod
    def _months_between(start_dt, end_dt):
        months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
        if end_dt < start_dt:
            months -= 1
        return max(1, months)

    # ---------------- SAVE ---------------- #

    def save(self, *args, **kwargs):
        self.full_clean()
        self.recalculate_totals()
        super().save(*args, **kwargs)

    # ---------------- PROPERTIES ---------------- #

    @property
    def is_upcoming(self):
        if self.start_datetime:
            return self.start_datetime > timezone.now()
        return False

    @property
    def is_ongoing(self):
        if self.start_datetime:
            now = timezone.now()
            return self.start_datetime <= now <= self.end_datetime
        return False

    def __str__(self):
        return f"Booking #{self.id} - {self.patient}"

class BookingService(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="booking_services",
        null=True, blank=True,
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)

    service = models.ForeignKey(
        "venue_manager.Service",
        on_delete=models.CASCADE,
        related_name="booking_instances",
    )

    service_package = models.ForeignKey(
        Package,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="service_bookings",
        limit_choices_to={"content_type__model": "service"},
    )

    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    status = models.CharField(
        max_length=25,
        choices=BookingStatus.choices,
        default=BookingStatus.DRAFT,
    )

    service_total_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_datetime"]
        indexes = [
            models.Index(fields=["booking", "service"]),
            models.Index(fields=["start_datetime", "end_datetime"]),
        ]

    def clean(self):
        if self.booking:
            if not (self.booking.start_datetime <= self.start_datetime <= self.booking.end_datetime):
                raise ValidationError("Service must start within booking range.")
            if self.end_datetime > self.booking.end_datetime:
                raise ValidationError("Service must end within booking range.")

    def calculate_cost(self):
        if not self.service_package:
            return Decimal("0.00")

        return Booking._calculate_package_cost(
            self.service_package,
            self.start_datetime,
            self.end_datetime,
        )

    def save(self, *args, **kwargs):
        self.full_clean()
        self.service_total_price = self.calculate_cost()
        if self.booking:
            self.patient = self.booking.patient
            self.user = self.booking.user
            self.booking.services_cost = self.service_total_price
            self.booking.save(update_fields=['services_cost'])
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        booking = self.booking
        super().delete(*args, **kwargs)
        if booking:
            booking.save()

    def __str__(self):
        return f"{self.service} | Booking #{self.booking_id}"


class InvoiceTransaction(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIALLY_PAID = "PARTIALLY_PAID", "Partially Paid"
        PAID = "PAID", "Paid"
        CANCELLED = "CANCELLED", "Cancelled"

    class PaymentType(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        REFUND = "REFUND", "Refund"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        UPI = "UPI", "UPI"
        CARD = "CARD", "Card"
        NET_BANKING = "NET_BANKING", "Net Banking"
        CHEQUE = "CHEQUE", "Cheque"

    class InvoiceFor(models.TextChoices):
        VENUE = "VENUE", "Venue"
        SERVICE = "SERVICE", "Service"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="invoices",
        null=True,
        blank=True,
    )

    invoice_for = models.CharField(
        max_length=20,
        choices=InvoiceFor.choices,
        default=InvoiceFor.VENUE,
        help_text="VENUE: venue + services | SERVICE: standalone services",
    )

    service_bookings = models.ManyToManyField(
        "BookingService",
        blank=True,
        related_name="invoices",
    )

    tax = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total_bill_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    paid_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    remain_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    transaction_type = models.CharField(
        max_length=15,
        choices=PaymentType.choices,
        default=PaymentType.PAYMENT,
        db_index=True,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    reference_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    remarks = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )

    notes = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name="invoices_created",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["booking", "invoice_for"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["transaction_type", "created_at"]),
            models.Index(fields=["reference_id"]),
        ]

    # --------------------------------------------------
    # BUSINESS LOGIC
    # --------------------------------------------------

    def calculate_amounts(self):
        """
        Calculate total_bill_amount based on invoice scope
        """

        total = Decimal("0.00")

        if self.invoice_for == self.InvoiceFor.VENUE and self.booking:
            total = (self.booking.final_amount or Decimal("0.00")) + self.tax

        elif self.invoice_for == self.InvoiceFor.SERVICE:
            total = (
                self.service_bookings.aggregate(
                    total=models.Sum("service_total_price")
                )["total"]
                or Decimal("0.00")
            )
        self.total_bill_amount = total
        self.remain_amount = max(
            Decimal("0.00"),
            self.total_bill_amount - self.paid_amount,
        )

    def update_payment_status(self):
        """
        Handles partial payments correctly
        """

        self.calculate_amounts()

        # Sum ALL payments except current instance (important!)
        previous_payments = (
            InvoiceTransaction.objects.filter(
                booking=self.booking,
                invoice_for=self.invoice_for,
                transaction_type=self.PaymentType.PAYMENT,
            )
            .exclude(pk=self.pk)
            .aggregate(total=models.Sum("paid_amount"))["total"]
            or Decimal("0.00")
        )

        refunds = (
            InvoiceTransaction.objects.filter(
                booking=self.booking,
                invoice_for=self.invoice_for,
                transaction_type=self.PaymentType.REFUND,
            )
            .exclude(pk=self.pk)
            .aggregate(total=models.Sum("paid_amount"))["total"]
            or Decimal("0.00")
        )

        total_paid = previous_payments + self.paid_amount - refunds

        self.remain_amount = max(
            Decimal("0.00"),
            self.total_bill_amount - total_paid
        )

        # Status
        if self.status == self.PaymentStatus.CANCELLED:
            return

        if self.remain_amount == 0:
            self.status = self.PaymentStatus.PAID
        elif total_paid > 0:
            self.status = self.PaymentStatus.PARTIALLY_PAID
        else:
            self.status = self.PaymentStatus.PENDING

    def is_overdue(self):
        return (
            self.due_date
            and self.due_date < timezone.now().date()
            and self.status != self.PaymentStatus.PAID
        )

    def save(self, *args, **kwargs):
        self.calculate_amounts()

        if self.transaction_type in {
            self.PaymentType.PAYMENT,
            self.PaymentType.REFUND,
        }:
            self.update_payment_status()

        super().save(*args, **kwargs)

    def __str__(self):
        invoice_scope = f"[{self.get_invoice_for_display()}]"

        if self.transaction_type == self.PaymentType.PAYMENT:
            return f"Payment #{self.id} {invoice_scope} | ₹{self.paid_amount}"

        if self.transaction_type == self.PaymentType.REFUND:
            return f"Refund #{self.id} {invoice_scope} | ₹{self.paid_amount}"

        return (
            f"Invoice #{self.id} {invoice_scope} "
            f"- {self.get_status_display()} | ₹{self.total_bill_amount}"
        )