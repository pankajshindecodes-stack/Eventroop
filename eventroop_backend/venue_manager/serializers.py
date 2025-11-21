from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from .models import Venue, Photos
from accounts.models import CustomUser


# --------------------------------------------------------
# PHOTO SERIALIZER
# --------------------------------------------------------
class PhotosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photos
        fields = ["id", "image", "is_primary", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


# --------------------------------------------------------
# VENUE SERIALIZER
# --------------------------------------------------------
class VenueSerializer(serializers.ModelSerializer):

    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    manager = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(
            user_type__in=["VSRE_MANAGER", "LINE_MANAGER"]
        ),
        required=False,
        allow_null=True
    )

    staff = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomUser.objects.filter(user_type="VSRE_STAFF"),
        required=False
    )

    photos_links = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Venue
        fields = [
            "id", "owner", "manager", "staff",
            "name", "description", "address","city",
            "primary_contact", "secondary_contact",
            "website", "social_links",
            "capacity", "price_per_event", "rooms", "floors",
            "parking_slots","external_decorators_allow", "external_caterers_allow",
            "amenities", "seating_arrangement",
            "is_active", "is_deleted",
            "created_at", "updated_at","photos_links",
        ]
        read_only_fields = ["is_deleted", "created_at", "updated_at"]

    # --------------------------------------------------------
    # CREATE VENUE WITH PHOTOS
    # --------------------------------------------------------
    def create(self, validated_data):
        photos_data = self.context['request'].FILES.getlist('photos')
        staff_data = validated_data.pop("staff", [])

        venue = Venue.objects.create(**validated_data)

        if staff_data:
            venue.staff.set(staff_data)

        if photos_data:
            ct = ContentType.objects.get_for_model(Venue)

            photo_objects = [
                Photos(
                        image=image,
                        is_primary=False, # TODO: need to manage primary image
                        content_type=ct,
                        object_id=venue.id,
                    )
                for image in photos_data
            ]
            # Bulk create → MUCH faster
            Photos.objects.bulk_create(photo_objects)

        return venue

    # --------------------------------------------------------
    # UPDATE VENUE + UPDATE/REPLACE PHOTOS
    # --------------------------------------------------------
    def update(self, instance, validated_data):
        photos_data = self.context['request'].FILES.getlist('photos')
        staff_data = validated_data.pop("staff", None)

        instance = super().update(instance, validated_data)

        # Update staff
        if staff_data is not None:
            instance.staff.set(staff_data)

        # Update photos
        if photos_data:
            ct = ContentType.objects.get_for_model(Venue)
            # Photos.objects.filter(content_type=ct, object_id=instance.id).delete()
            photo_objects = [
                Photos(
                        image=image,
                        is_primary=False, # TODO: need to create separate api to manage photos
                        content_type=ct,
                        object_id=instance.id,
                    )
                for image in photos_data
            ]
            # Bulk create → MUCH faster
            Photos.objects.bulk_create(photo_objects)
            

        return instance
    

    # --------------------------------------------------------
    # GET PHOTO
    # --------------------------------------------------------
    def get_photos_links(self, obj):
        photos = obj.photos.all()  # all photos
        return PhotosSerializer(photos, many=True).data

