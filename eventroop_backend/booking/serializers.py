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


