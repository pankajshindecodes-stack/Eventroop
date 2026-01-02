from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html

from .models import Photos, Venue, Service, Resource

class PhotosInline(GenericTabularInline):
    model = Photos
    extra = 1
    fields = ("image", "is_primary", "preview")
    readonly_fields = ("preview",)

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit:cover;border-radius:4px;" />',
                obj.image.url,
            )
        return "-"
    preview.short_description = "Preview"

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "city",
        "is_active",
        "is_deleted",
        "created_at",
    )
    list_filter = ("is_active", "is_deleted", "city")
    search_fields = ("name", "city", "address")
    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at")

    filter_horizontal = ("manager", "staff")
    inlines = [PhotosInline]

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "description", "logo")
        }),
        ("Location", {
            "fields": ("address", "city")
        }),
        ("Ownership", {
            "fields": ("owner", "manager", "staff")
        }),
        ("Contact", {
            "fields": ("contact", "website", "social_links")
        }),
        ("Capacity & Pricing", {
            "fields": ("capacity", "price_per_event", "rooms", "floors")
        }),
        ("Amenities", {
            "fields": ("amenities", "seating_arrangement")
        }),
        ("Permissions", {
            "fields": ("external_decorators_allow", "external_caterers_allow")
        }),
        ("Status", {
            "fields": ("is_active", "is_deleted")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "city",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "city")
    search_fields = ("name", "description")
    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at")

    filter_horizontal = ("manager", "staff")
    inlines = [PhotosInline]

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "description", "logo")
        }),
        ("Location", {
            "fields": ("address", "city")
        }),
        ("Ownership", {
            "fields": ("owner", "manager", "staff")
        }),
        ("Contact", {
            "fields": ("contact", "website")
        }),
        ("Relations", {
            "fields": ("venue",)
        }),
        ("Tags & Extra Info", {
            "fields": ("tags", "quick_info")
        }),
        ("Status", {
            "fields": ("is_active", "is_deleted")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )
@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "available_quantity",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    ordering = ("-created_at",)

    readonly_fields = ("created_at", "updated_at")

    filter_horizontal = ("manager", "staff")
    inlines = [PhotosInline]

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "description")
        }),
        ("Location", {
            "fields": ("address",)
        }),
        ("Ownership", {
            "fields": ("owner", "manager", "staff")
        }),
        ("Inventory", {
            "fields": (
                "total_quantity",
                "available_quantity",
                "sell_price_per_unit",
                "rent_price_per_unit_per_day",
            )
        }),
        ("Relations", {
            "fields": ("venue", "service")
        }),
        ("Tags", {
            "fields": ("tags",)
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

@admin.register(Photos)
class PhotosAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "content_object",
        "is_primary",
        "uploaded_at",
        "preview",
    )
    list_filter = ("is_primary",)
    readonly_fields = ("uploaded_at", "preview")

    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit:cover;" />',
                obj.image.url,
            )
        return "-"
    preview.short_description = "Preview"
