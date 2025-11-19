from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from accounts.models import CustomUser

# ----------------------------- Photo for all -----------------------
class Photos(models.Model):
    """Generic model to support multiple photos for any entity."""
    image = models.ImageField(upload_to="entety_photos/",null=True,blank=True,)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Generic Foreign Key to link to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        ordering = ["-is_primary", "uploaded_at"]
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"Photo for {self.content_object} ({'primary' if self.is_primary else 'secondary'})"

# ----------------------------- Location for all  -----------------------

# ----------------------------- Venue -----------------------
class Venue(models.Model):
    # User Relationships
    
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="venues",
        limit_choices_to={"user_type": "VSRE_OWNER"},
    )
    manager = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_venues",
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER"]},
    )
    staff = models.ManyToManyField(
        CustomUser,
        related_name='assigned_venues',
        blank=True,
        limit_choices_to={"user_type": "VSRE_STAFF"},
        help_text="Staff assigned to this venue"
    )

    
    # Venue Details
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.TextField()
    primary_contact = models.CharField(max_length=15, blank=True, null=True)
    secondary_contact = models.CharField(max_length=15, blank=True, null=True)
    website = models.URLField(max_length=500,blank=True,null=True,help_text="Official website ")
    social_links = models.JSONField(blank=True, null=True)

    # Capacity related
    capacity = models.PositiveIntegerField(default=0, help_text="Total pax capacity")
    price_per_event = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    rooms = models.PositiveSmallIntegerField(default=0)
    floors = models.PositiveSmallIntegerField(default=0)

    # Parking
    parking_slots = models.JSONField(default=dict, blank=True, null=True)

    # External vendor permissions
    external_decorators_allow = models.BooleanField(default=False)
    external_caterers_allow = models.BooleanField(default=False)

    # Amenities & seating
    amenities = models.JSONField(default=list, blank=True, null=True)
    seating_arrangement = models.JSONField(default=list, blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def photos(self):
        """Get all photos for this venue"""
        return Photos.objects.filter_by_instance(self)
    
    @property
    def primary_photo(self):
        """Get primary photo for this venue"""
        return self.photos.filter(is_primary=True).first()
    
    def soft_delete(self):
        self.is_active = False
        self.is_deleted = True
        self.save()
    
    def __str__(self):
        return f"{self.name} ({self.id})"

# ----------------------------- Service -----------------------
class Service(models.Model):
    """Caterers, Decorators, Photographers, etc."""
    
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="services",
        limit_choices_to={"user_type": "VSRE_OWNER"},
    )
    manager = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_services",
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER"]},
    )
    staff = models.ManyToManyField(
        CustomUser,
        related_name='assigned_services',
        blank=True,
        limit_choices_to={"user_type": "VSRE_STAFF"},
        help_text="Staff assigned to this service"
    )
      # Optional Relation
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, related_name="services_of_venue")
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    address = models.TextField()
    primary_contact = models.CharField(max_length=15, unique=True)
    secondary_contact = models.CharField(max_length=15, unique=True, blank=True, null=True)
    website = models.URLField(max_length=500,blank=True,null=True,help_text="Official website")

    tags = models.JSONField(default=list, blank=True, null=True)
    quickInfo = models.JSONField(blank=True, null=True) # TODO: need to create separate model for this 
    is_active = models.BooleanField(default=True)


    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    @property
    def photos(self):
        """Get all photos for this service"""
        return Photos.objects.filter_by_instance(self)
    
    @property
    def primary_photo(self):
        """Get primary photo for this service"""
        return self.photos.filter(is_primary=True).first()

    def __str__(self):
        return f"{self.name} ({self.owner})"

# ----------------------------- Resource -----------------------
class Resource(models.Model):
    """Physical inventory like Tables, Chairs, Carpets, Fans"""
     
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="resource",
        limit_choices_to={"user_type": "VSRE_OWNER"},
    )
    manager = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_resource",
        limit_choices_to={"user_type__in": ["VSRE_MANAGER", "LINE_MANAGER"]},
    )
    staff = models.ManyToManyField(
        CustomUser,
        related_name='assigned_resource',
        blank=True,
        limit_choices_to={"user_type": "VSRE_STAFF"},
        help_text="Staff assigned to this resource"
    )

    name = models.CharField(max_length=200)
    address = models.TextField()
    description = models.TextField(blank=True)

    total_quantity = models.PositiveIntegerField(default=1)
    available_quantity = models.PositiveIntegerField(default=1)
    sell_price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rent_price_per_unit_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tags = models.JSONField(default=list, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    # Optional Relation
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True, related_name="resources_of_venue")
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, blank=True, related_name="resources_of_service")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def photos(self):
        """Get all photos for this resource"""
        return Photos.objects.filter_by_instance(self)
    
    @property
    def primary_photo(self):
        """Get primary photo for this resource"""
        return self.photos.filter(is_primary=True).first()

    def __str__(self):
        return f"{self.name} ({self.owner})"