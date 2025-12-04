from django.contrib import admin
from .models import Patient

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
        'is_active',
    )

    list_filter = (
        'gender',
        'blood_group',
        'id_proof',
        'payment_mode',
        'is_active',
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
