from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from .models import Photos, Venue, Service, Resource

# ----------------------------- Inline Admin for Photos -----------------------
class PhotosInline(GenericTabularInline):
    model = Photos
    extra = 1
    readonly_fields = ['uploaded_at']
    fields = ['image', 'is_primary', 'uploaded_at']

# ----------------------------- Photos Admin -----------------------
@admin.register(Photos)
class PhotosAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_object', 'is_primary', 'uploaded_at']
    list_filter = ['is_primary', 'uploaded_at', 'content_type']
    search_fields = ['content_object__name']
    readonly_fields = ['uploaded_at']
    list_select_related = ['content_type']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('content_type')

# ----------------------------- Venue Admin -----------------------
@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'owner', 'manager', 'capacity', 'price_per_event', 
        'is_active', 'is_deleted', 'created_at'
    ]
    list_filter = [
        'is_active', 'is_deleted', 'external_decorators_allow', 
        'external_caterers_allow', 'created_at'
    ]
    search_fields = ['name', 'address', 'primary_contact', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['staff']
    
    fieldsets = (
        ('Owner & Management', {
            'fields': ('owner', 'manager', 'staff')
        }),
        ('Venue Details', {
            'fields': (
                'name', 'description', 'address', 
                'primary_contact', 'secondary_contact',
                'website', 'social_links'
            )
        }),
        ('Capacity & Pricing', {
            'fields': (
                'capacity', 'price_per_event', 'rooms', 'floors'
            )
        }),
        ('Parking & Amenities', {
            'fields': (
                'parking_slots', 'amenities', 'seating_arrangement'
            )
        }),
        ('External Vendor Permissions', {
            'fields': (
                'external_decorators_allow', 'external_caterers_allow'
            )
        }),
        ('Status', {
            'fields': ('is_active', 'is_deleted')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PhotosInline]
    
    actions = ['activate_venues', 'deactivate_venues', 'soft_delete_venues']
    
    def activate_venues(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} venues activated successfully.')
    activate_venues.short_description = "Activate selected venues"
    
    def deactivate_venues(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} venues deactivated successfully.')
    deactivate_venues.short_description = "Deactivate selected venues"
    
    def soft_delete_venues(self, request, queryset):
        for venue in queryset:
            venue.soft_delete()
        self.message_user(request, f'{queryset.count()} venues soft deleted successfully.')
    soft_delete_venues.short_description = "Soft delete selected venues"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner', 'manager')

# ----------------------------- Service Admin -----------------------
@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'owner', 'manager', 'primary_contact', 'venue', 
        'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'address', 'primary_contact', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['staff']
    
    fieldsets = (
        ('Owner & Management', {
            'fields': ('owner', 'manager', 'staff')
        }),
        ('Service Details', {
            'fields': (
                'name', 'description', 'address', 
                'primary_contact', 'secondary_contact',
                'website', 'tags', 'quickInfo'
            )
        }),
        ('Venue Relation', {
            'fields': ('venue',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PhotosInline]
    
    actions = ['activate_services', 'deactivate_services']
    
    def activate_services(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} services activated successfully.')
    activate_services.short_description = "Activate selected services"
    
    def deactivate_services(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} services deactivated successfully.')
    deactivate_services.short_description = "Deactivate selected services"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner', 'manager', 'venue')

# ----------------------------- Resource Admin -----------------------
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'owner', 'manager', 'total_quantity', 'available_quantity',
        'rent_price_per_unit_per_day', 'is_active', 'created_at'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'address', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['staff']
    
    fieldsets = (
        ('Owner & Management', {
            'fields': ('owner', 'manager', 'staff')
        }),
        ('Resource Details', {
            'fields': (
                'name', 'description', 'address', 'tags'
            )
        }),
        ('Inventory & Pricing', {
            'fields': (
                'total_quantity', 'available_quantity',
                'sell_price_per_unit', 'rent_price_per_unit_per_day'
            )
        }),
        ('Relations', {
            'fields': ('venue', 'service')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [PhotosInline]
    
    actions = ['activate_resources', 'deactivate_resources']
    
    def activate_resources(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} resources activated successfully.')
    activate_resources.short_description = "Activate selected resources"
    
    def deactivate_resources(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} resources deactivated successfully.')
    deactivate_resources.short_description = "Deactivate selected resources"
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('owner', 'manager', 'venue', 'service')