from django.contrib import admin
from django.db.models import Sum
from .models import (
    Location, Package, Patient, InvoiceBooking, 
    TotalInvoice, Payment
)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('building_name', 'city', 'location_type', 'postal_code')
    list_filter = ('location_type', 'city', 'state')
    search_fields = ('building_name', 'city', 'address_line1')
    readonly_fields = ('full_address',)
    
    fieldsets = (
        ('Location Details', {
            'fields': ('location_type', 'user')
        }),
        ('Address', {
            'fields': ('building_name', 'address_line1', 'address_line2', 'locality', 'city', 'state', 'postal_code', 'full_address')
        }),
    )

@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'belongs_to', 'package_type', 'period', 'price', 'is_active')
    list_filter = ('package_type', 'period', 'is_active', 'created_at')
    search_fields = ('name', 'owner__email')
    readonly_fields = ('belongs_to','created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'owner')
        }),
        ('Package Details', {
            'fields': ('package_type', 'period', 'price', 'is_active')
        }),
        ('Polymorphic Relation', {
            'fields': ('content_type', 'object_id','belongs_to'),
            # 'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'email', 'phone', 'gender', 'blood_group', 'registration_date')
    list_filter = ('gender', 'blood_group', 'registration_date', 'id_proof')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    readonly_fields = ('registration_date', 'updated_at', 'get_total_payment')
    date_hierarchy = 'registration_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'email', 'registered_by')
        }),
        ('Contact Information', {
            'fields': ('phone', 'address', 'age')
        }),
        ('Emergency Contacts', {
            'fields': ('emergency_contact', 'emergency_phone', 'emergency_contact_2', 'emergency_phone_2')
        }),
        ('Medical Information', {
            'fields': ('gender', 'blood_group', 'medical_conditions', 'allergies', 'present_health_condition', 'preferred_language')
        }),
        ('Identification', {
            'fields': ('id_proof', 'id_proof_number', 'patient_documents')
        }),
        ('Professional Background', {
            'fields': ('education_qualifications', 'earlier_occupation', 'year_of_retirement'),
            'classes': ('collapse',)
        }),
        ('Payment Information', {
            'fields': ('registration_fee', 'advance_payment', 'payment_mode', 'get_total_payment')
        }),
        ('Metadata', {
            'fields': ('registration_date', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'



# Payments Inline (inside Invoice)
class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("created_at",)


# Monthly Invoice Admin

@admin.register(TotalInvoice)
class TotalInvoiceAdmin(admin.ModelAdmin):

    list_display = (
        "invoice_number",
        "booking",
        "period_start",
        "period_end",
        "total_amount",
        "paid_amount",
        "remaining_amount",
        "status",
    )

    list_filter = ("status", "period_start")

    search_fields = ("invoice_number",)

    readonly_fields = ("paid_amount", "remaining_amount")

    inlines = [PaymentInline]

    def save_model(self, request, obj, form, change):
        """
        Auto recalc paid + remaining whenever admin saves.
        """
        super().save_model(request, obj, form, change)

        payments = obj.payments.aggregate(total=Sum("amount"))["total"] or 0

        obj.paid_amount = payments
        obj.remaining_amount = obj.total_amount - payments

        if obj.remaining_amount <= 0:
            obj.status = "PAID"

        obj.save(update_fields=["paid_amount", "remaining_amount", "status"])



# Booking Inline (services under venue)


class ServiceBookingInline(admin.TabularInline):
    model = InvoiceBooking
    fk_name = "parent"
    extra = 0
    show_change_link = True



# InvoiceBooking Admin


@admin.register(InvoiceBooking)
class InvoiceBookingAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "booking_entity",
        "user",
        "venue",
        "service",
        "start_datetime",
        "end_datetime",
        "subtotal",
        "status",
    )

    list_filter = ("booking_entity", "status")

    search_fields = ("id",)

    inlines = [ServiceBookingInline]

    readonly_fields = ("subtotal",)

    fieldsets = (
        ("Core", {
            "fields": (
                "booking_entity",
                "parent",
                "user",
                "patient",
                "status",
            )
        }),
        ("Entities", {
            "fields": (
                "venue",
                "service",
                "package",
            )
        }),
        ("Period", {
            "fields": (
                "start_datetime",
                "end_datetime",
            )
        }),
        ("Financial", {
            "fields": ("subtotal",),
        }),
    )

    def get_queryset(self, request):
        """
        Only show parent bookings by default.
        """
        qs = super().get_queryset(request)
        return qs.filter(parent__isnull=True)
