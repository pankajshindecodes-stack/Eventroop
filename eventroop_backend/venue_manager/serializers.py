from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from .models import *
from accounts.models import CustomUser


# --------------------------------------------------------
# PHOTO SERIALIZER
# --------------------------------------------------------
class PhotosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photos
        fields = "__all__"
        read_only_fields = ["id", "uploaded_at"]

class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "first_name", "last_name", "email", "mobile_number", "user_type"]

class LocationMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = [
            "building_name",
            "address_line1",
            "address_line2",
            "locality",
            "city",
            "state",
            "postal_code",
        ]


# --------------------------------------------------------
# VENUE SERIALIZER
# --------------------------------------------------------
class VenueSerializer(serializers.ModelSerializer):
    photos = PhotosSerializer(many=True, read_only=True)
    owner = UserMiniSerializer(read_only=True)
    manager = UserMiniSerializer(many=True, read_only=True)
    staff = UserMiniSerializer(many=True, read_only=True)

    location = LocationMiniSerializer(read_only=True)

    class Meta:
        model = Venue
        fields = [
            "id", "owner", "manager", "staff",
            "name", "description","location",
            "capacity", "price_per_event", "rooms", "floors",
            "parking_slots", "external_decorators_allow",
            "external_caterers_allow", "amenities",
            "seating_arrangement",
            "is_active", "is_deleted",
            "created_at", "updated_at",
            "photos", "logo"
        ]
        read_only_fields = ["is_deleted", "created_at", "updated_at"]

    # --------------------------------------------------------
    # CREATE
    # --------------------------------------------------------
    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]

        photos_data = request.FILES.getlist("photos")
        logo = request.FILES.get("logo")

        location_data = validated_data.pop("location")
        location_data["location_type"] = "OPD"

        # Create location
        location = Location.objects.create(**location_data)

        # Create venue
        venue = Venue.objects.create(
            **validated_data,
            location=location,
            logo=logo
        )

        # Save photos
        if photos_data:
            ct = ContentType.objects.get_for_model(Venue)
            Photos.objects.bulk_create([
                Photos(
                    image=image,
                    is_primary=False,
                    content_type=ct,
                    object_id=venue.id,
                )
                for image in photos_data
            ])

        return venue

    # --------------------------------------------------------
    # UPDATE
    # --------------------------------------------------------
    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context["request"]

        photos_data = request.FILES.getlist("photos")
        logo = request.FILES.get("logo")

        # Update location
        location_data = validated_data.pop("location", None)
        if location_data:
            for attr, value in location_data.items():
                setattr(instance.location, attr, value)
            instance.location.save()

        # Update venue fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if logo:
            instance.logo = logo

        instance.save()

        # Add new photos (no delete)
        if photos_data:
            ct = ContentType.objects.get_for_model(Venue)
            Photos.objects.bulk_create([
                Photos(
                    image=image,
                    is_primary=False,
                    content_type=ct,
                    object_id=instance.id,
                )
                for image in photos_data
            ])

        return instance

# --------------------------------------------------------
# SERVICE SERIALIZER
# --------------------------------------------------------
class ServiceSerializer(serializers.ModelSerializer):
    photos = PhotosSerializer(many=True, read_only=True)

    owner = UserMiniSerializer(read_only=True)
    manager = UserMiniSerializer(many=True, read_only=True)
    staff = UserMiniSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = [
            "id", "owner", "manager", "staff", "venue",
            "name", "description", "address","city",
            "contact","website", "tags", "quick_info",
            "is_active", "is_deleted",
            "created_at", "updated_at",
            "photos","logo"
        ]
        read_only_fields = ["created_at", "updated_at"]

    # --------------------------------------------------------
    # CREATE SERVICE WITH PHOTOS
    # --------------------------------------------------------
    def create(self, validated_data):
        photos_data = self.context["request"].FILES.getlist("photos")
        validated_data["logo"] = self.context["request"].FILES.get("logo")

        
        service = Service.objects.create(**validated_data)
        
        if photos_data:
            ct = ContentType.objects.get_for_model(Service)
            photo_objs = [
                Photos(
                    image=image,
                    is_primary=False,
                    content_type=ct,
                    object_id=service.id,
                )
                for image in photos_data
            ]
            Photos.objects.bulk_create(photo_objs)

        return service

    # --------------------------------------------------------
    # UPDATE SERVICE + OPTIONAL PHOTO UPDATE
    # --------------------------------------------------------
    def update(self, instance, validated_data):
        photos_data = self.context["request"].FILES.getlist("photos")
        validated_data["logo"] = self.context["request"].FILES.get("logo")

        instance = super().update(instance, validated_data)

        if photos_data:
            ct = ContentType.objects.get_for_model(Service)
            photo_objs = [
                Photos(
                    image=image,
                    is_primary=False,
                    content_type=ct,
                    object_id=instance.id,
                )
                for image in photos_data
            ]
            Photos.objects.bulk_create(photo_objs)

        return instance
    