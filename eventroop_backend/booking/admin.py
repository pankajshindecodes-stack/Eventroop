from django.contrib import admin
from .models import *
from django.contrib.contenttypes.models import ContentType

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "location_type",
        "user",
        "building_name",
        'locality',
        "city",
        "postal_code",
    )

    list_filter = (
        "location_type",
        "city",
        "state",
    )

    search_fields = (
        "building_name",
        "address_line1",
        "address_line2",
        "locality",
        "city",
        "state",
        "postal_code",
    )

    ordering = ("city", "building_name")

    readonly_fields = ()

    fieldsets = (
        ("Location Type", {
            "fields": ("location_type",)
        }),
        ("Building Information", {
            "fields": ("building_name",)
        }),
        ("Address", {
            "fields": (
                "address_line1",
                "address_line2",
                "locality",
                "city",
                "state",
                "postal_code",
            )
        }),
    )

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "package_type",
        "price",
        "owner",
        "belongs_to_object",
        "is_active",
        "created_at",
    )

    list_filter = ("package_type", "is_active", "created_at", "content_type")
    search_fields = ("name", "owner__first_name", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("owner",)

    fieldsets = (
        ("Package Info", {
            "fields": ("name", "description", "package_type", "price", "is_active")
        }),
        ("Owner", {
            "fields": ("owner",)
        }),
        ("Linked To", {
            "fields": ("content_type", "object_id")
        }),
        ("System", {
            "fields": ("created_at", "updated_at")
        }),
    )

    # -------------------------------------------------
    # 🔒 Restrict ContentType → Only Venue & Service
    # -------------------------------------------------
    def formfield_for_foreignkey(self, db_field, request, **kwargs):

        if db_field.name == "content_type":
            allowed_models = ["venue", "service"]

            kwargs["queryset"] = ContentType.objects.filter(
                model__in=allowed_models
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # -------------------------------------------------
    # Polymorphic display
    # -------------------------------------------------
    def belongs_to_object(self, obj):
        if obj.belongs_to:
            return f"{obj.belongs_to}"
        return "-"

    belongs_to_object.short_description = "Belongs To"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "owner",
            "content_type"
        )

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'first_name',
        'last_name',
        'phone',
        'email',
        'gender',
        'blood_group',
        'registered_by',
        'registration_date',
    )

    list_filter = (
        'gender',
        'blood_group',
        'id_proof',
        'payment_mode',
        'registered_by',
        'registration_date',
    )

    search_fields = (
        'first_name',
        'last_name',
        'phone',
        'email',
        'id_proof_number',
    )

    readonly_fields = (
        'registration_date',
        'updated_at',
    )

    ordering = ('-registration_date',)

    list_per_page = 25

    # Improve performance
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('registered_by')
