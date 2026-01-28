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

class PatientMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='get_full_name',read_only=True)
    class Meta:
        model = Patient
        fields = [
            'name',
            'email',
            'phone',
            'age',
            'emergency_contact',
            'emergency_phone',
        ]

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
    belongs_to_type = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = [
            'id', 'name', 'package_type',
            'price', 'is_active', 'belongs_to_type',
        ]

    def get_belongs_to_type(self, obj):
        return obj.content_type.model if obj.content_type else None


class InvoiceBookingServiceSerializer(serializers.ModelSerializer):
    """Serializer for invoice booking services"""
    service_name = serializers.CharField(source='service.name', read_only=True)
    service_package_name = serializers.CharField(source='service_package.name', read_only=True)
    
    class Meta:
        model = InvoiceBookingService
        fields = [
            'id',
            'invoice_number',
            'service_id',
            'service_name',
            'service_package_name',
            'start_datetime',
            'end_datetime',
            'subtotal',
            'status',
            'booking_type',
        ]
        read_only_fields = ['invoice_number', 'subtotal', 'created_at']

class InvoiceBookingSerializer(serializers.ModelSerializer):
    """Serializer for venue bookings"""
    patient = PatientMiniSerializer(read_only=True)
    patient_id = serializers.IntegerField(required=True,source="patient.id")
    user_id = serializers.IntegerField(source='user.id',read_only=True)
    user_name = serializers.CharField(source='user.get_full_name',read_only=True)

    venue_name = serializers.CharField(source='venue.name', read_only=True)
    package_name = serializers.CharField(source='venue_package.name', read_only=True)
    services = InvoiceBookingServiceSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(
        source="invoice.total_amount",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    class Meta:
        model = InvoiceBooking
        fields = [
            'id',
            'invoice_number',
            'user_id',
            'user_name',
            'venue_id',
            'venue_name',
            'package_name',
            'start_datetime',
            'end_datetime',
            'subtotal',
            'total_amount',
            'status',
            'booking_type',
            'patient_id',
            'patient',
            'services',
        ]
        read_only_fields = ['invoice_number','patient', 'subtotal', 'created_at']


class BookServiceSerializer(serializers.Serializer):
    """Serializer for booking a service"""
    service_id = serializers.IntegerField()
    service_package_id = serializers.IntegerField()
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
    booking_type = serializers.CharField(required=False, allow_null=True)
    invoice_booking_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if data['start_datetime'] >= data['end_datetime']:
            raise serializers.ValidationError("start_datetime must be before end_datetime")
        return data


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments"""
    class Meta:
        model = Payment
        fields = ['id', 'amount', 'method', 'reference']
        read_only_fields = ['created_at']


class TotalInvoiceSerializer(serializers.ModelSerializer):
    """Serializer for total invoices"""
    booking = InvoiceBookingSerializer(read_only=True)
    services = InvoiceBookingServiceSerializer(source='service_bookings', many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    
    class Meta:
        model = TotalInvoice
        fields = [
            'id',
            'patient_id',
            'user_id',
            'total_amount',
            'paid_amount',
            'remaining_amount',
            'status',
            'due_date',
            'booking',
            'services',
            'payments',
            'created_at'
        ]
        read_only_fields = ['total_amount', 'paid_amount', 'remaining_amount', 'created_at']
