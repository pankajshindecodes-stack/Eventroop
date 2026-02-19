from rest_framework import serializers
from django.db import transaction
from .models import *
from .constants import *
from django.contrib.contenttypes.models import ContentType

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
        return obj.user.get_full_name() if obj.user else None

class PatientSerializer(serializers.ModelSerializer):
    name_registered_by = serializers.CharField(
        source="registered_by.get_full_name", read_only=True
    )
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Patient
        fields = "__all__"
        read_only_fields = [
            "id",
            "patient_id",
            "name_registered_by",
            "registered_by",
            "registration_date",
            
        ]

class PatientMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = Patient
        fields = [
            "id",
            "patient_id",
            "name",
            "email",
            "phone",
            "age",
            "emergency_contact",
            "emergency_phone",
        ]

class PackageSerializer(serializers.ModelSerializer):
    belongs_to_type = serializers.CharField(write_only=True)
    belongs_to_detail = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source="owner.get_full_name", read_only=True)

    class Meta:
        model = Package
        fields = [
            "id",
            "owner",
            "owner_name",
            "name",
            "description",
            "package_type",
            "price",
            "is_active",
            "object_id",
            "belongs_to_type",
            "belongs_to_detail",
        ]

        read_only_fields = [
            "id",
            "owner",
            "owner_name",
        ]
        write_only_fields = [
            "object_id",
        ]
    # Convert model name → content_type
    def validate(self, attrs):
        model_name = attrs.pop("belongs_to_type", None)

        if model_name:
            try:
                content_type = ContentType.objects.get(model=model_name.lower())
                attrs["content_type"] = content_type
                
            except ContentType.DoesNotExist:
                raise serializers.ValidationError(
                    {"belongs_to_type": "Invalid model name."}
                )
        if not attrs.get("content_type",None):
            raise serializers.ValidationError(
                {"belongs_to_type": "this field is required."}
            )
        return attrs
    
    def get_belongs_to_detail(self, obj):
        if obj.belongs_to:
            return {
                "id": obj.object_id,
                "type": obj.content_type.model,
                "name": str(obj.belongs_to),
            }
        return None

    def validate_owner(self, value):
        if value.user_type != "VSRE_OWNER":
            raise serializers.ValidationError("Owner must be a VSRE_OWNER user type.")
        return value

class PackageListSerializer(serializers.ModelSerializer):
    belongs_to_type = serializers.CharField(source='content_type.model',read_only=True)
    belong_to = serializers.CharField(source='belongs_to',read_only=True)

    class Meta:
        model = Package
        fields = ["id", "name", "price", "is_active","package_type", "belong_to","belongs_to_type"]

class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    class Meta:
        model = Payment
        fields = [
            'id',
            'amount',
            'method',
            'paid_date',
            'reference',
            'is_verified'
        ]
        read_only_fields = ['id', 'reference',]

class NestedInvoiceBookingSerializer(serializers.ModelSerializer):
    """Nested serializer for child InvoiceBooking entries"""
    service_name = serializers.CharField(
        source='service.name',
        read_only=True,
        allow_null=True
    )
    class Meta:
        model = InvoiceBooking
        fields = [
            'id',
            'booking_entity',
            'order_id',
            'service',
            'service_name',
            'subtotal',
            'booking_type',
            'status',
            'start_datetime',
            'end_datetime',
            'auto_continue',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'subtotal','order_id','created_at','updated_at']

class InvoiceBookingSerializer(serializers.ModelSerializer):
    """Serializer for InvoiceBooking model with nested children"""
    
    children = NestedInvoiceBookingSerializer(
        many=True,
        read_only=True
    )
    venue_name = serializers.CharField(
        source='venue.name',
        read_only=True,
        allow_null=True
    )
    service_name = serializers.CharField(
        source='service.name',
        read_only=True,
        allow_null=True
    )
    package_name = serializers.CharField(
        source='package.name',
        read_only=True,
        allow_null=True
    )
    patient = PatientMiniSerializer(read_only=True)

    user_email = serializers.CharField(
        source='user.email',
        read_only=True
    )

    
    class Meta:
        model = InvoiceBooking
        fields = [
            'id',
            'order_id',
            'booking_entity',
            'booking_type',
            'status',
            'patient',
            'user',
            'user_email',
            'venue',
            'venue_name',
            'service',
            'service_name',
            'package',
            'package_name',
            'subtotal',
            'start_datetime',
            'end_datetime',
            'auto_continue',
            'children',
        ]
        read_only_fields = ['id', 'subtotal','order_id']
    
    def validate(self, data):
        """Validate booking entity and required fields"""
        booking_entity = data.get('booking_entity')
        
        if booking_entity == 'VENUE' and not data.get('venue'):
            raise serializers.ValidationError(
                "Venue booking requires a venue to be specified."
            )
        
        if booking_entity == 'SERVICE' and not data.get('service'):
            raise serializers.ValidationError(
                "Service booking requires a service to be specified."
            )
        
        # Validate datetime range
        if data.get('start_datetime') and data.get('end_datetime'):
            if data['start_datetime'] >= data['end_datetime']:
                raise serializers.ValidationError(
                    "Start datetime must be before end datetime."
                )
        
        return data

class TotalInvoiceSerializer(serializers.ModelSerializer):
    """
        Unified serializer for both list and detail views
    """

    payments = PaymentSerializer(
        many=True,
        read_only=True
    )

    patient_name = serializers.CharField(
        source="patient.get_full_name",
        read_only=True
    )

    user_name = serializers.CharField(
        source="user.get_full_name",
        read_only=True
    )

    venue_name = serializers.CharField(
        source="booking.venue.name",
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = TotalInvoice
        fields = [
            # core
            "id",
            "invoice_number",
            "status",

            # relations
            "booking",
            "patient",
            "patient_name",
            "user",
            "user_name",
            "venue_name",

            # period
            "period_start",
            "period_end",

            # amounts
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "tax_amount",

            # dates
            "issued_date",
            "due_date",

            # nested
            "payments",
        ]

        read_only_fields = [
            "id",
            "invoice_number",
            "total_amount",
            "remaining_amount",
            "paid_amount",
            "issued_date",
        ]

    def validate_discount_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Discount amount cannot be negative."
            )
        return value

    def validate_tax_amount(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Tax amount cannot be negative."
            )
        return value

class PaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payments"""
    
    class Meta:
        model = Payment
        fields = [
            'amount',
            'method',
            'reference',
            'paid_date',
            'is_verified'
        ]
    
    def validate_amount(self, value):
        """Validate payment amount is positive"""
        if value <= 0:
            raise serializers.ValidationError(
                "Payment amount must be greater than zero."
            )
        return value

class InvoiceBookingCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new invoice bookings"""
    
    class Meta:
        model = InvoiceBooking
        fields = [
            'patient',
            'venue',
            'package',
            'start_datetime',
            'end_datetime',
            'auto_continue',
        ]
        extra_kwargs = {
            "venue": {"required": True},
        }
    
    def validate(self, data):
        """
        Validate datetime range safely for create & update.
        """

        # Use instance fallback for partial update
        start_datetime = data.get(
            "start_datetime",
            getattr(self.instance, "start_datetime", None)
        )
        end_datetime = data.get(
            "end_datetime",
            getattr(self.instance, "end_datetime", None)
        )

        # Validate datetime range
        if start_datetime and end_datetime:
            if start_datetime >= end_datetime:
                raise serializers.ValidationError({
                    "start_datetime": "Start datetime must be before end datetime."
                })

        return data

class ServiceBookingCreateSerializer(serializers.ModelSerializer):
    """
    Create SERVICE booking under VENUE booking via action API.
    Parent injected from ViewSet.
    """

    class Meta:
        model = InvoiceBooking
        fields = [
            "service",
            "package",
            "start_datetime",
            "end_datetime",
            "auto_continue",
            "discount_amount",
            "premium_amount",
        ]

    def validate(self, attrs):
        parent = self.context.get("parent")

        if not parent:
            raise serializers.ValidationError({
                "parent": "Parent booking missing."
            })

        # Use instance fallback for update cases
        service = attrs.get(
            "service",
            getattr(self.instance, "service", None)
        )

        booking_entity = getattr(parent, "booking_entity", None)

        #  Parent must be VENUE
        if booking_entity != BookingEntity.VENUE:
            raise serializers.ValidationError({
                "parent": "Parent must be VENUE booking."
            })

        #  Service required
        if not service:
            raise serializers.ValidationError({
                "service": "Service is required."
            })

        #  Child date validation (important)
        start_datetime = attrs.get(
            "start_datetime",
            getattr(self.instance, "start_datetime", None)
        )
        end_datetime = attrs.get(
            "end_datetime",
            getattr(self.instance, "end_datetime", None)
        )

        if start_datetime and end_datetime:
            if start_datetime >= end_datetime:
                raise serializers.ValidationError({
                    "start_datetime": "Start must be before end."
                })

            if (
                start_datetime < parent.start_datetime or
                end_datetime > parent.end_datetime
            ):
                raise serializers.ValidationError({
                    "start_datetime": "Service booking must be within Venue booking dates."
                })

        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        parent = self.context["parent"]
        validated_data["parent"] = parent
        validated_data["user"] = parent.user
        validated_data["patient"] = parent.patient
        validated_data["booking_entity"] = BookingEntity.SERVICE
        validated_data["booking_type"] = BookingType.OPD
        return InvoiceBooking.objects.create(**validated_data)

class InvoiceSummarySerializer(serializers.Serializer):
    """Serializer for invoice summary/statistics"""

    total_invoices = serializers.IntegerField()
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    paid_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    remaining_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    unpaid_count = serializers.IntegerField()
    partially_paid_count = serializers.IntegerField()
    paid_count = serializers.IntegerField()