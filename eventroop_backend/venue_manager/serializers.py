# serializers.py
from rest_framework import serializers
from .models import Venue, Photos,VSREOwnerProfile, VSREStaffProfile, VSREManagerProfile, Location

class LocationSerializer(serializers.ModelSerializer):
    full_address = serializers.ReadOnlyField()

    class Meta:
        model = Location
        fields = [
            "id",
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "country",
            "postal_code",
            "full_address",
        ]

class PhotoSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()
    class Meta:
        model = Photos
        fields = ["id", "image", "is_primary", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]
    
    def get_image(obj):
        return obj.image.url if obj else None

class VenueSerializer(serializers.ModelSerializer):
    # Nested read-only data for existing photos
    photos_data = PhotoSerializer(source='photos', many=True, read_only=True)
    location = LocationSerializer()
    
    # Write-only field for uploading new photos
    new_photos = serializers.ListField( 
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        allow_empty=True
    )

    owner = serializers.PrimaryKeyRelatedField(
        queryset=VSREOwnerProfile.objects.all(),  
        required=False,
        allow_null=True
    )

    manager = serializers.PrimaryKeyRelatedField(
        queryset=VSREManagerProfile.objects.all(),
        required=False,
        allow_null=True
    )
    
    staff = serializers.PrimaryKeyRelatedField(
        queryset=VSREStaffProfile.objects.all(),
        many=True,
        required=False
    )

    class Meta:
        model = Venue
        fields = [
            'id', 'owner', 'manager', 'staff', 'name', 'location', 'description',
            'capacity', 'price_per_event', 'rooms', 'floors', 'parking_slots',
            'external_decorators_allow', 'external_caterers_allow',
            'amenities', 'seating_arrangement', 'is_active', 'is_deleted',
            'created_at', 'updated_at', 'new_photos', 'photos_data'
        ]
        read_only_fields = ('id', 'owner', 'created_at', 'updated_at', 'is_deleted')

    def create(self, validated_data):
        request = self.context.get('request')
        if not request or not request.user:
            raise serializers.ValidationError("Request context is required")
        
        user = request.user

        # Auto-assign owner
        if hasattr(user, 'owner_profile'):
            validated_data['owner'] = user.owner_profile
        else:
            raise serializers.ValidationError(
                {"owner": "Only owners can create venues."}
            )

        # Extract related data
        new_photos = validated_data.pop('new_photos', [])  # CHANGED: photos → new_photos
        staff_data = validated_data.pop('staff', [])
        location_data = validated_data.pop('location')

        # Create related location
        location = Location.objects.create(**location_data)

        # Create main venue
        venue = Venue.objects.create(location=location, **validated_data)

        # Add staff ManyToMany
        if staff_data:
            print("staff_data:", staff_data)
            venue.staff.set(staff_data)

        # Add photos
        for img in new_photos: 
            Photos.objects.create(venue=venue, image=img)

        return venue

    def update(self, instance, validated_data):
        # Extract related data
        new_photos = validated_data.pop('new_photos', [])  
        staff_data = validated_data.pop('staff', None)
        location_data = validated_data.pop('location', None)

        # Update location if provided
        if location_data:
            location_serializer = LocationSerializer(
                instance.location, 
                data=location_data, 
                partial=True
            )
            if location_serializer.is_valid():
                location_serializer.save()
            else:
                raise serializers.ValidationError({
                    "location": location_serializer.errors
                })

        # Update main venue instance
        instance = super().update(instance, validated_data)

        # Update staff if provided
        if staff_data is not None:
            instance.staff.set(staff_data)

        # Add new photos
        for img in new_photos:
            Photos.objects.create(venue=instance, image=img)

        return instance