from rest_framework import serializers
from .models import *
from rest_framework import serializers
from .models import Location


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

