from rest_framework import serializers
from venue_manager.models import Venue, Service
from venue_manager.serializers import PhotosSerializer
from .models import Patient


class VenueSerializer(serializers.ModelSerializer):
    photos  = PhotosSerializer(many=True, read_only=True)

    class Meta:
        model = Venue
        fields = "__all__"
        
class ServiceSerializer(serializers.ModelSerializer):
    photos  = PhotosSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = "__all__"
        

class PatientSerializer(serializers.ModelSerializer):
    name_registered_by = serializers.CharField(source="registered_by.get_full_name")
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ['id', 'registered_by','name_registered_by' 'registration_date', 'updated_at']
