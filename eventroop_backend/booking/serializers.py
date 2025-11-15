from rest_framework import serializers
from venue_manager.models import Venue, Photos, Location
from venue_manager.serializers import LocationSerializer,PhotoSerializer

class VenueSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    photos = PhotoSerializer(many=True, read_only=True)

    class Meta:
        model = Venue
        fields = "__all__"
