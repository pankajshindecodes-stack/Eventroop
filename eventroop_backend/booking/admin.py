from django.contrib import admin
from .models import Patient,Location


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "location_type",
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
