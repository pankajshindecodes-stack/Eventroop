from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta, datetime
from accounts.models import CustomUser
from venue_manager.models import Venue, Service
from django.db import transaction
from .models import *
from .utils import calculate_package_cost
from .constants import *

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
            "name",
            "email",
            "phone",
            "age",
            "emergency_contact",
            "emergency_phone",
        ]

class PackageSerializer(serializers.ModelSerializer):
    belongs_to_type = serializers.SerializerMethodField()
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
            "content_type",
            "object_id",
            "belongs_to_type",
            "belongs_to_detail",
        ]

        read_only_fields = [
            "id",
            "owner",
            "owner_name",
        ]

    def get_belongs_to_type(self, obj):
        return obj.content_type.model if obj.content_type else None

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
            'reference',
            'is_verified',
            'created_at'
        ]
        read_only_fields = ['id', 'reference', 'created_at']


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
            'service',
            'service_name',
            'subtotal',
            'booking_type',
            'status',
            'start_datetime',
            'end_datetime',
        ]
        read_only_fields = ['id', 'subtotal']


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
            'children',
        ]
        read_only_fields = ['id', 'subtotal']
    
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
            "discount_amount",
            "tax_amount",

            # dates
            "issued_date",
            "due_date",
            "paid_date",

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
        ]
        extra_kwargs = {
            "venue": {"required": True},
        }
    
    def validate(self, data):
        """Validate booking entity and required fields"""
        
        # Validate datetime range
        if data.get('start_datetime') and data.get('end_datetime'):
            if data['start_datetime'] >= data['end_datetime']:
                raise serializers.ValidationError(
                    {"start_datetime": "Start datetime must be before end datetime."}
                )
        
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
            "discount_amount",
            "premium_amount",
        ]

    def validate(self, attrs):
        parent = self.context.get("parent")

        if not parent:
            raise serializers.ValidationError("Parent booking missing.")

        if parent.booking_entity != BookingEntity.VENUE:
            raise serializers.ValidationError("Parent must be VENUE booking.")

        if not attrs.get("service"):
            raise serializers.ValidationError("Service is required.")

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        parent = self.context["parent"]
        validated_data["parent"] = parent
        validated_data["user"] = parent.user
        validated_data["patient"] = parent.patient
        validated_data["booking_entity"] = BookingEntity.SERVICE
        validated_data["booking_type"] = BookingType.OPD
        validated_data["status"] = BookingStatus.BOOKED
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