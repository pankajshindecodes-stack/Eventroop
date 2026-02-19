from django.db import models,transaction
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import CustomUser
from django.contrib.contenttypes import fields, models as ct_models
from decimal import Decimal
import uuid
from .constants import *
from datetime import timedelta
from dateutil.relativedelta import relativedelta

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
        ct_models.ContentType,
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
    belongs_to = fields.GenericForeignKey('content_type', 'object_id')

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

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        super().save(*args, **kwargs)

        # After first save, ID exists
        if is_new and not self.patient_id:
            self.patient_id = f"{self.pk:05}"
            super().save(update_fields=["patient_id"])

class InvoiceBooking(models.Model):
    order_id = models.CharField(max_length=50, blank=True)

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
    auto_continue = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        """
        Safe string representation with null checks.
        """
        if self.booking_entity == BookingEntity.SERVICE:
            entity = str(self.service) if self.service else "Unknown Service"
        elif self.booking_entity == BookingEntity.VENUE:
            entity = str(self.venue) if self.venue else "Unknown Venue"
        else:
            entity = "Unknown"
        
        patient_name = self.patient.get_full_name() if self.patient else "Unknown Patient"
        
        return (
            f"#{self.pk} | "
            f"{self.get_booking_entity_display()} | "
            f"{patient_name} | "
            f"{entity}"
        )

    def save(self, *args, **kwargs):
        """
        Calculate subtotal and create invoices for new bookings.
        """
        skip_update_auto_status = kwargs.pop('skip_update_auto_status', False)
        if not skip_update_auto_status:
            self._update_status_automatically()
            
        # Calculate subtotal
        subtotal = self._calculate_subtotal()
        self.subtotal = (subtotal - self.discount_amount) + self.premium_amount
        
        super().save(*args, **kwargs)
        
        # Only create for fulfilled statuses
        if self.status not in {
            BookingStatus.FULFILLED,
            BookingStatus.PARTIALLY_FULFILLED,
        }:
            return

        # Only for standalone bookings
        if self.parent is not None:
            return

        # Avoid duplicate invoices
        if self.invoices.exists():
            return
        self._create_monthly_invoices()
        

    def _update_status_automatically(self):
        now = timezone.now()

        if now < self.start_datetime:
            self.status = BookingStatus.YET_TO_START

        elif self.start_datetime <= now <= self.end_datetime:
            self.status = BookingStatus.IN_PROGRESS

        elif now > self.end_datetime:
            self.status = BookingStatus.UNFULFILLED

    def _calculate_subtotal(self):
        """Calculate base subtotal before discounts/premiums."""
        from .utils import calculate_package_cost
        return calculate_package_cost(
            self.package,
            self.start_datetime,
            self.end_datetime
        )

    def _create_monthly_invoices(self):
        """
        Create monthly invoices when booking spans multiple months.
        Called automatically during save() for new bookings.
        
        For a booking from Feb 1 - Apr 30:
        - Invoice 1: Feb 1 - Feb 29 (February)
        - Invoice 2: Mar 1 - Mar 31 (March)
        - Invoice 3: Apr 1 - Apr 30 (April)
        """
        with transaction.atomic():
            months_to_invoice = self._get_month_periods()
            
            for period_start, period_end in months_to_invoice:
                # Check if invoice already exists
                existing_invoice = TotalInvoice.objects.filter(
                    booking=self,
                    period_start=period_start,
                    period_end=period_end
                ).first()
                
                if existing_invoice:
                    # Already exists, recalculate
                    existing_invoice.recalculate_totals()
                    continue
                
                # Create new invoice
                invoice = TotalInvoice.objects.create(
                    booking=self,
                    period_start=period_start,
                    period_end=period_end,
                    patient=self.patient,
                    user=self.user
                )
                
                # Calculate totals
                invoice.recalculate_totals()

    def _get_month_periods(self):
        """
        Split datetime range into monthly periods.
        
        Returns:
            list: [(period_start, period_end), ...]
        """
        if self.start_datetime >= self.end_datetime:
            return []

        periods = []
        current = self.start_datetime

        while current < self.end_datetime:
            # Calculate the last moment of the current month
            first_of_next_month = (
                current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                + relativedelta(months=1)
            )
            
            # Last moment of current month
            last_of_current_month = first_of_next_month - timedelta(microseconds=1)
            
            # Period end is the minimum of last day of month or booking end
            period_end = min(last_of_current_month, self.end_datetime)
            
            periods.append((current, period_end))
            
            # Next period starts immediately after current period ends
            current = period_end + timedelta(microseconds=1)

        return periods

    def _get_months_count(self):
        """
        Calculate number of months this booking spans.
        
        Returns:
            int: Number of months (including partial months)
        
        Example:
            2026-02-15 to 2026-04-25 = 3 months
            2026-02-01 to 2026-02-28 = 1 month
        """
        if self.start_datetime >= self.end_datetime:
            return 0
        
        months = 0
        current = self.start_datetime
        
        while current < self.end_datetime:
            months += 1
            current = current + relativedelta(months=1)
        
        return months

    def cancel(self):
        """
        Cancel this booking and all its child bookings.
        Automatically updates invoices.
        """
        if self.status == BookingStatus.CANCELLED:
            return

        with transaction.atomic():
            # Update children first
            self.children.update(
                status=BookingStatus.CANCELLED,
                subtotal=Decimal("0.00")
            )
            
            # Update self
            self.status = BookingStatus.CANCELLED
            self.subtotal = Decimal("0.00")
            self.save(update_fields=["status", "subtotal"])
            
            # Update associated invoices
            invoices = TotalInvoice.objects.filter(booking=self)
            for invoice in invoices:
                if invoice.paid_amount == 0:
                    invoice.status = InvoiceStatus.CANCELLED
                    invoice.save(update_fields=['status'])
                else:
                    # Recalculate with cancelled booking
                    invoice.recalculate_totals()

    def reschedule(self, new_start_datetime, new_end_datetime, new_package_id=None,discount_amount=None,premium_amount=None):
        now = timezone.now()

        if new_start_datetime >= new_end_datetime:
            raise ValidationError("Start date must be before end date")

        is_ongoing = self.start_datetime <= now <= self.end_datetime
        is_upcoming = self.start_datetime > now
        is_past = self.end_datetime < now
        
        # Past booking cannot be modified
        if is_past:
            raise ValidationError("Past bookings cannot be modified")

        # Ongoing booking rules
        if is_ongoing:

            # Allow only end date change
            if new_start_datetime != self.start_datetime:
                raise ValidationError(
                    "Start date cannot be modified for partially fulfilled booking"
                )

        # Upcoming → allow full modification
        with transaction.atomic():
            old_start = self.start_datetime

            self.start_datetime = new_start_datetime
            self.end_datetime = new_end_datetime

            if new_package_id:
                self.package_id = new_package_id
            if discount_amount:
                self.discount_amount = discount_amount
            if premium_amount:
                self.premium_amount = premium_amount

            self.save(skip_update_auto_status=True)

            self._recalculate_invoices()

            # Shift children if start changed
            if new_start_datetime != old_start:
                time_diff = new_start_datetime - old_start

                for child in self.children.all():
                    if child.start_datetime > now:
                        child.start_datetime += time_diff
                        child.end_datetime += time_diff
                        child.save()
                        child._recalculate_invoices()

    def _recalculate_invoices(self):
        """Recalculate all associated invoices."""
        invoices = TotalInvoice.objects.filter(booking=self)
        for invoice in invoices:
            invoice.recalculate_totals()

    def get_booking_invoice_info(self):
        """
        Get comprehensive invoice information for this booking.
        
        Returns:
            dict: Invoice summary information
        """
        invoices = self.invoices.all()
        
        total_amount = sum(inv.total_amount for inv in invoices)
        total_paid = sum(inv.paid_amount for inv in invoices)
        total_remaining = sum(inv.remaining_amount for inv in invoices)
        
        return {
            'booking_id': self.id,
            'booking_entity': self.get_booking_entity_display(),
            'months_count': self._get_months_count(),
            'month_periods': [
                {
                    'period_start': start.isoformat(),
                    'period_end': end.isoformat(),
                }
                for start, end in self._get_month_periods()
            ],
            'invoices_count': invoices.count(),
            'invoices': [
                {
                    'id': inv.id,
                    'invoice_number': inv.invoice_number,
                    'period': f"{inv.period_start.date()} - {inv.period_end.date()}",
                    'total_amount': str(inv.total_amount),
                    'paid_amount': str(inv.paid_amount),
                    'remaining_amount': str(inv.remaining_amount),
                    'status': inv.get_status_display(),
                    'due_date': inv.due_date,
                }
                for inv in invoices.order_by('period_start')
            ],
            'total_invoice_amount': str(total_amount),
            'total_paid': str(total_paid),
            'total_remaining': str(total_remaining),
        }

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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True
    )

    class Meta:
        ordering = ['-issued_date']
        indexes = [
            models.Index(fields=['booking', 'period_start']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.period_start.date()} to {self.period_end.date()}"
    
    def save(self, *args, **kwargs):
        from .utils import generate_order_id

        is_new = self.pk is None

        super().save(*args, **kwargs)  # Save first to get PK

        if is_new and not self.invoice_number:
            self.invoice_number = "INV"+ generate_order_id(
                instance=self,
                created_by=self.user
            )
            super().save(update_fields=["invoice_number"])
        
    def recalculate_totals(self):
        """
        Recalculate invoice total amount based on current booking and children.
        Uses update() to avoid triggering save signals.
        """
        # Calculate venue subtotal
        venue_subtotal = self._calculate_venue_subtotal()
        
        # Calculate services subtotal for this period
        services_subtotal = self._calculate_services_subtotal()

        subtotal = venue_subtotal + services_subtotal
        self.total_amount = subtotal + (self.tax_amount or Decimal("0"))
        self.remaining_amount = self.total_amount - (self.paid_amount or Decimal("0"))
        super().save(update_fields=["total_amount","remaining_amount"])
        
    def _calculate_venue_subtotal(self):
        """Calculate venue/parent booking cost for this period."""
        from .utils import calculate_package_cost
        
        subtotal = calculate_package_cost(
            self.booking.package,
            self.period_start,
            self.period_end
        )
        
        # Ensure Decimal type and handle None
        return Decimal(str(subtotal or "0"))

    def _calculate_services_subtotal(self):
        """Calculate all child services cost for this period."""
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        
        services_subtotal = self.booking.children.filter(
            start_datetime__lte=self.period_end,
            end_datetime__gte=self.period_start
        ).aggregate(
            total=Coalesce(Sum("subtotal"), Decimal("0.00"))
        )["total"]
        
        return services_subtotal or Decimal("0.00")

    def recalculate_payments(self):
        """
        Recalculate paid amount and invoice status based on recorded payments.
        Called when payments are added or modified.
        """
        from django.db.models import Sum
        from django.db.models.functions import Coalesce
        
        paid = self.payments.aggregate(
            total=Coalesce(Sum("amount"), Decimal("0"))
        )["total"]

        self.paid_amount = paid or Decimal("0")
        self.remaining_amount = max(self.total_amount - self.paid_amount, Decimal("0"))

        # Determine status
        if self.paid_amount == 0:
            self.status = InvoiceStatus.UNPAID
        elif self.paid_amount >= self.total_amount:
            self.status = InvoiceStatus.PAID
        else:
            self.status = InvoiceStatus.PARTIALLY_PAID

        # Use update() to avoid triggering post_save
        super().save(
            update_fields=[
                "paid_amount",
                "remaining_amount",
                "status",
            ]
        )
        
        
        
        # Refresh from DB
        self.refresh_from_db()

    def get_payments_info(self):
        """Get summary of all payments for this invoice."""
        payments = self.payments.all()
        
        return {
            'invoice_id': self.id,
            'invoice_number': self.invoice_number,
            'total_due': str(self.total_amount),
            'paid': str(self.paid_amount),
            'remaining': str(self.remaining_amount),
            'status': self.get_status_display(),
            'payment_count': payments.count(),
            'payments': [
                {
                    'id': p.id,
                    'amount': str(p.amount),
                    'method': p.method,
                    'date': p.paid_date.isoformat(),
                    'reference': p.reference or '-',
                    'is_verified': p.is_verified,
                }
                for p in payments.order_by('-paid_date')
            ]
        }

class Payment(models.Model):

    invoice = models.ForeignKey(
        TotalInvoice,
        related_name="payments",
        on_delete=models.CASCADE
    )

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    paid_date = models.DateTimeField(default=timezone.now)

    reference = models.CharField(max_length=100, blank=True)
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_date']
        indexes = [
            models.Index(fields=['invoice', 'created_at']),
            models.Index(fields=['is_verified']),
        ]

    def __str__(self):
        return f"Payment {self.id} - {self.amount} for Invoice {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        """
        Save payment and recalculate invoice status.
        all logic is here.
        """
        if not self.reference:
            self.reference = f"PAY-{uuid.uuid4().hex[:10].upper()}"

        super().save(*args, **kwargs)
        
        # Recalculate invoice status after payment is recorded
        self.invoice.recalculate_payments()

    def verify(self):
        """
        Mark payment as verified and recalculate invoice status.
        
        Returns:
            bool: True if verification was successful
        """
        if self.is_verified:
            return False  # Already verified
        
        with transaction.atomic():
            self.is_verified = True
            self.save(update_fields=['is_verified'])
            
            # Recalculate invoice
            self.invoice.recalculate_payments()
            
            return True

    def unverify(self):
        """
        Mark payment as unverified and recalculate invoice status.
        
        Returns:
            bool: True if unverification was successful
        """
        if not self.is_verified:
            return False  # Not verified
        
        with transaction.atomic():
            self.is_verified = False
            self.save(update_fields=['is_verified'])
            
            # Recalculate invoice
            self.invoice.recalculate_payments()
            
            return True