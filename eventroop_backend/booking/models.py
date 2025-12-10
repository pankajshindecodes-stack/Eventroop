from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import CustomUser

class Patient(models.Model):
    """Model for storing patient registration and medical information"""
    
    # Gender Choices
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer-not-to-say', 'Prefer not to say'),
    ]
    
    # Blood Group Choices
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
    
    # ID Proof Choices
    ID_PROOF_CHOICES = [
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('passport', 'Passport'),
        ('driving-license', 'Driving License'),
        ('voter-id', 'Voter ID'),
        ('other', 'Other'),
    ]
        
    # Payment Mode Choices
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('credit-card', 'Credit Card'),
        ('debit-card', 'Debit Card'),
        ('net-banking', 'Net Banking'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('bank-transfer', 'Bank Transfer'),
    ]
    
    # Phone number validator
    phone_regex = RegexValidator(
        regex=r'^\d{10}$',
        message="Phone number must be 10 digits"
    )
    
    # PAN validator
    pan_regex = RegexValidator(
        regex=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$',
        message="PAN must be in format: ABCDE1234F"
    )
    
    # Aadhar validator
    aadhar_regex = RegexValidator(
        regex=r'^\d{12}$',
        message="Aadhar must be 12 digits"
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
    email = models.EmailField(null=True,blank=True)
    
    # Contact Information
    phone = models.CharField(max_length=10, validators=[phone_regex])
    address = models.TextField()
    
    # Date of Birth / Age
    age = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    
    # Emergency Contacts
    emergency_contact = models.CharField(max_length=100)
    emergency_phone = models.CharField(max_length=10, validators=[phone_regex])
    
    emergency_contact_2 = models.CharField(max_length=100,null=True, blank=True)
    emergency_phone_2 = models.CharField(max_length=10,null=True, blank=True, validators=[phone_regex])
    
    # Medical Information
    medical_conditions = models.TextField(null=True,blank=True)
    allergies = models.TextField(null=True,blank=True)
    present_health_condition = models.TextField(null=True,blank=True)
    
    # Personal Details
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    blood_group = models.CharField(max_length=3, choices=BLOOD_GROUP_CHOICES,null=True, blank=True)
    preferred_language = models.CharField(max_length=20,null=True, blank=True)
    
    # Identification
    id_proof = models.CharField(max_length=20, choices=ID_PROOF_CHOICES)
    id_proof_number = models.CharField(max_length=50)
    patient_documents = models.FileField(upload_to='patient_documents/',help_text="Upload related document")
    
    # Professional Background
    education_qualifications = models.TextField(null=True,blank=True)
    earlier_occupation = models.CharField(max_length=200,null=True, blank=True)
    year_of_retirement = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1950), MaxValueValidator(timezone.now().year)]
    )
    
    # Payment Information 
    # TODO: need to move in payment table
    registration_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=5000.00
    )
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
    
    # Metadata
    registration_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
        
    class Meta:
        ordering = ['-registration_date']
        verbose_name = 'Patient'
        verbose_name_plural = 'Patients'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['phone']),
            models.Index(fields=['-registration_date']),
            models.Index(fields=['registered_by']),

        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.email}"
    
    def get_full_name(self):
        """Returns the patient's full name"""
        return f"{self.first_name} {self.last_name}"
      
    def get_total_payment(self):
        """Returns total payment (registration fee + advance payment)"""
        total = self.registration_fee
        if self.advance_payment:
            total += self.advance_payment
        return total
    
    def clean(self):
        """Custom validation"""       
        # Validate ID proof number based on type
        if self.id_proof == 'aadhar' and self.id_proof_number:
            if not self.id_proof_number.isdigit() or len(self.id_proof_number) != 12:
                raise ValidationError('Aadhar number must be 12 digits')
        
        if self.id_proof == 'pan' and self.id_proof_number:
            if len(self.id_proof_number) != 10:
                raise ValidationError('PAN number must be 10 characters')
        
        # Validate payment mode if advance payment is provided
        if self.advance_payment and self.advance_payment > 0 and not self.payment_mode:
            raise ValidationError('Payment mode is required when advance payment is provided')
    
    def save(self, *args, **kwargs):
        """Override save to perform additional operations"""
        self.full_clean()
        super().save(*args, **kwargs)