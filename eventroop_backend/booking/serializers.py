from rest_framework import serializers
from venue_manager.models import Venue, Photos
from venue_manager.serializers import PhotosSerializer

class VenueSerializer(serializers.ModelSerializer):
    photos  = PhotosSerializer(many=True, read_only=True)

    class Meta:
        model = Venue
        fields = "__all__"
        
