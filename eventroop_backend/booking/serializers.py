from rest_framework import serializers
from venue_manager.models import Venue
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
            "updated_at",
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
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "content_type",
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
    belongs_to_type = serializers.SerializerMethodField()

    class Meta:
        model = Package
        fields = ["id", "name", "package_type", "price", "is_active", "belongs_to_type"]

    def get_belongs_to_type(self, obj):
        return obj.content_type.model if obj.content_type else None

class InvoiceBookingServiceSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_package_name = serializers.CharField(
        source="service_package.name", read_only=True
    )

    class Meta:
        model = InvoiceBookingService
        fields = [
            "id",
            "service_id",
            "service_name",
            "service_package_id",
            "service_package_name",
            "start_datetime",
            "end_datetime",
            "status",
            "booking_type",
        ]

        read_only_fields = ["subtotal"]

class InvoiceBookingSerializer(serializers.ModelSerializer):
    # Read-only nested
    patient = PatientMiniSerializer(read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    user_name = serializers.CharField(source="user.get_full_name", read_only=True)
    venue_name = serializers.CharField(source="venue.name", read_only=True)
    package_name = serializers.CharField(source="venue_package.name", read_only=True)
    services = InvoiceBookingServiceSerializer(many=True, read_only=True)

    # Writeable fields
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=Patient.objects.all(),
        source="patient",
        write_only=True,
    )
    venue_id = serializers.PrimaryKeyRelatedField(
        queryset=Venue.objects.all(),
        source="venue",
        write_only=True,
    )
    venue_package_id = serializers.PrimaryKeyRelatedField(
        queryset=Package.objects.all(),
        source="venue_package",
        write_only=True,
    )

    class Meta:
        model = InvoiceBooking
        fields = [
            "id",
            "user_id",
            "user_name",
            "venue_id",
            "venue_name",
            "venue_package_id",
            "package_name",
            "start_datetime",
            "end_datetime",
            "status",
            "booking_type",
            "patient_id",
            "patient",
            "services",
        ]
        read_only_fields = ["subtotal"]

class BookServiceSerializer(serializers.Serializer):
    service_id = serializers.IntegerField()
    service_package_id = serializers.IntegerField()
    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()
    booking_type = serializers.CharField(required=False, allow_null=True)
    invoice_booking_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if data["start_datetime"] >= data["end_datetime"]:
            raise serializers.ValidationError(
                "start_datetime must be before end_datetime"
            )
        return data

class PaymentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Payment
        fields = [
            'id',
            'invoice',
            'amount',
            'method',
            'reference',
            'is_verified',
            'created_at',
            
        ]
        read_only_fields = [
            "patient",
            "is_verified",
            "created_at",
            "updated_at",
        ]

class TotalInvoiceListSerializer(serializers.ModelSerializer):
    payments = PaymentSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source="patient.get_full_name", read_only=True)

    class Meta:
        model = TotalInvoice
        fields = [
            "id",
            "invoice_number",
            "patient",
            "patient_name",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "status",
            "due_date",
            "created_at",
            "payments",
        ]
