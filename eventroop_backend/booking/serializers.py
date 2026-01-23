from rest_framework import serializers
from .models import *

class LocationSerializer(serializers.ModelSerializer):
    full_address = serializers.SerializerMethodField(read_only=True)
    user_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Location
        fields = [
            "id",
            "user",
            "user_name",
            "location_type",
            "building_name",
            "address_line1",
            "address_line2",
            "locality",
            "city",
            "state",
            "postal_code",
            "full_address",
        ]
        read_only_fields = ["user"]
    def get_full_address(self, obj):
        return obj.full_address()
    
    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return None

class PatientSerializer(serializers.ModelSerializer):
    name_registered_by = serializers.CharField(source="registered_by.get_full_name",read_only=True)
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ['id','name_registered_by', 'registered_by', 'registration_date', 'updated_at']

class PackageSerializer(serializers.ModelSerializer):
    belongs_to_type = serializers.SerializerMethodField()
    belongs_to_detail = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)

    class Meta:
        model = Package
        fields = [
            'id', 'owner', 'owner_name', 'name', 'description',
            'package_type', 'price', 'is_active', 'content_type',
            'object_id', 'belongs_to_type', 'belongs_to_detail',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'content_type', 'owner','owner_name']

    def get_belongs_to_type(self, obj):
        if obj.content_type:
            return obj.content_type.model
        return None

    def get_belongs_to_detail(self, obj):
        if obj.belongs_to:
            return {
                'id': obj.object_id,
                'type': obj.content_type.model,
                'name': str(obj.belongs_to)
            }
        return None

    def validate_owner(self, value):
        if value.user_type != "VSRE_OWNER":
            raise serializers.ValidationError(
                "Owner must be a VSRE_OWNER user type."
            )
        return value

class PackageListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    belongs_to_type = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'owner_name', 'name', 'package_type',
            'price', 'is_active', 'belongs_to_type', 'created_at'
        ]

    def get_belongs_to_type(self, obj):
        return obj.content_type.model if obj.content_type else None

    def clean(self):
        """Validate booking data"""
        if self.end_datetime <= self.start_datetime:
            raise ValidationError("End time must be after start time.")
        
        if self.start_datetime < timezone.localtime() and self.status == "DRAFT":
            raise ValidationError("Cannot book for past dates.")
        
        if self.final_amount < 0:
            raise ValidationError("Final amount cannot be negative.")
        
        if self.discount > self.subtotal:
            raise ValidationError("Discount cannot exceed subtotal.")


class BookingListSerializer(serializers.ModelSerializer):
    """Detailed serializer for retrieving single booking"""
    # User Data
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    # Patient Data
    patient_name = serializers.CharField(source='patient.get_full_name', read_only=True)
    patient_age = serializers.CharField(source='patient.age', read_only=True)
    patient_emergency_contact = serializers.CharField(source='patient.emergency_contact', read_only=True)
    patient_emergency_phone = serializers.CharField(source='patient.emergency_phone', read_only=True)

    venue_name = serializers.CharField(source='venue.name', read_only=True, allow_null=True)
    venue_package_name = serializers.CharField(source='venue_package.name', read_only=True, allow_null=True)
    is_upcoming = serializers.SerializerMethodField()
    is_ongoing = serializers.SerializerMethodField()
    
    class Meta:
        model = Booking
        fields = [
            # user data
            'id', 'user','user_email','user_name', 
            # patient data
            'patient','patient_name','patient_age','patient_emergency_contact','patient_emergency_phone',
            #  venue data
            'venue', 'venue_name', 'venue_package', 'venue_package_name',
            # Booking datails
            'start_datetime', 'end_datetime', 'venue_cost', 'services_cost',
            'subtotal', 'discount', 'final_amount', 'status', 'continue_booking',
            'is_upcoming', 'is_ongoing',
        ]
        read_only_fields = [
            'id', 'user_email','user_name', 
            'patient_name','patient_age','patient_emergency_contact','patient_emergency_phone',

            'venue_name', 'venue_package_name', 'venue_cost', 'services_cost', 'subtotal',
                'final_amount', 'is_upcoming', 'is_ongoing',
            'created_at', 'updated_at'
        ]
    
    def get_is_upcoming(self, obj):
        return obj.is_upcoming
    
    def get_is_ongoing(self, obj):
        return obj.is_ongoing
    
class BookingCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating venue bookings"""
    
    class Meta:
        model = Booking
        fields = [
            'patient', 'venue', 'venue_package',
            'start_datetime', 'end_datetime', 'discount', 'continue_booking'
        ]
    
    def validate_start_datetime(self, value):
        if value < timezone.now():
            raise serializers.ValidationError("Start datetime cannot be in the past.")
        return value
    
    def validate(self, data):
        start_dt = data.get('start_datetime')
        end_dt = data.get('end_datetime')
        
        # Validate datetime range
        if start_dt and end_dt and start_dt >= end_dt:
            raise serializers.ValidationError({
                'end_datetime': "End datetime must be after start datetime."
            })
        
        # Ensure venue and venue_package are provided
        venue = data.get('venue')
        venue_package = data.get('venue_package')
        
        if not venue or not venue_package:
            raise serializers.ValidationError({
                'venue': "Venue and venue package are required for venue booking."
            })
        
        # Validate venue_package belongs to venue
        if venue_package.content_type.model != 'venue':
            raise serializers.ValidationError({
                'venue_package': "Selected package is not a venue package."
            })
        
        # Validate discount
        discount = data.get('discount', Decimal('0.00'))
        if discount < 0:
            raise serializers.ValidationError({
                'discount': "Discount cannot be negative."
            })
        
        # Check for venue availability (optional - customize as needed)
        self._check_venue_availability(venue, start_dt, end_dt)
        
        return data
    
    def _check_venue_availability(self, venue, start_dt, end_dt):
        """Check if venue is available for the given time slot"""
        conflicting_bookings = Booking.objects.filter(
            venue=venue,
            status__in=['BOOKED', 'IN_PROGRESS'],
            start_datetime__lt=end_dt,
            end_datetime__gt=start_dt
        )
        
        if conflicting_bookings.exists():
            raise serializers.ValidationError({
                'venue': "Venue is not available for the selected time period."
            })

class BookingServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source='service.name', read_only=True)
    
    class Meta:
        model = BookingService

        fields = [
            'id', 
            'booking',
            'user',
            'patient',
            'service',
            'service_name',
            'service_package',
            'start_datetime',
            'end_datetime',
            'status',
            'service_total_price',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['status','service_total_price', 'created_at']
    
    def validate(self, data):
        if data['start_datetime'] > data['end_datetime']:
            raise serializers.ValidationError("End datetime must be after start datetime.")
        return data


class InvoiceTransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display", read_only=True
    )
    transaction_type_display = serializers.CharField(
        source="get_transaction_type_display", read_only=True
    )
    invoice_for_display = serializers.CharField(
        source="get_invoice_for_display", read_only=True
    )
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = InvoiceTransaction
        fields = [
            "id",
            "booking",
            "invoice_for",
            "invoice_for_display",
            "service_bookings",
            "tax",
            "total_bill_amount",
            "paid_amount",
            "remain_amount",
            "transaction_type",
            "transaction_type_display",
            "payment_method",
            "payment_method_display",
            "invoice_id",
            "remarks",
            "status",
            "status_display",
            "notes",
            "due_date",
            "created_by",
            "created_at",
            "updated_at",
            "is_overdue",
        ]
        read_only_fields = [
            "id",
            "invoice_id",
            "remain_amount",
            "total_bill_amount",
            "created_at",
            "updated_at",
        ]

    def get_is_overdue(self, obj):
        return obj.is_overdue()

class CreatePaymentSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(required=False, allow_null=True)
    invoice_for = serializers.ChoiceField(
        choices=InvoiceTransaction.InvoiceFor.choices
    )
    paid_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    payment_method = serializers.ChoiceField(
        choices=InvoiceTransaction.PaymentMethod.choices
    )
    transaction_type = serializers.ChoiceField(
        choices=[
            InvoiceTransaction.PaymentType.PAYMENT,
            InvoiceTransaction.PaymentType.REFUND,
        ],
        default=InvoiceTransaction.PaymentType.PAYMENT,
    )
    service_bookings = serializers.PrimaryKeyRelatedField(
        queryset=BookingService.objects.all(),
        many=True,
        required=False,
    )
    remarks = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateField(required=False, allow_null=True)

class InvoiceSummarySerializer(serializers.Serializer):
    total_invoices = serializers.IntegerField()
    total_bill_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2
    )
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_pending = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_refunded = serializers.DecimalField(max_digits=12, decimal_places=2)
    overdue_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    by_status = serializers.DictField()
    by_payment_method = serializers.DictField()

