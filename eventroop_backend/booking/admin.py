from django.contrib import admin
from django.utils.html import format_html
from .models import *

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
    list_display = ('name', 'owner', 'package_type', 'period', 'price', 'is_active')
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
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('content_type', 'object_id')
        return self.readonly_fields


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

# -------------------------
# Inline: Booking Services
# -------------------------
class BookingServiceInline(admin.TabularInline):
    model = BookingService
    extra = 0

    autocomplete_fields = (
        "service",
        "service_package",
    )

    readonly_fields = (
        "service_total_price",
        "created_at",
        "updated_at",
    )

    fields = (
        "service",
        "service_package",
        "start_datetime",
        "end_datetime",
        "status",
        "service_total_price",
    )

    show_change_link = True



# -------------------------
# Booking Admin
# -------------------------
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "user",
        "venue",
        "status_badge",
        "start_datetime",
        "end_datetime",
        "subtotal",
        "discount",
        "final_amount",
        "booking_state",
        "created_at",
    )

    list_filter = (
        "status",
        "venue",
        "created_at",
        "start_datetime",
    )

    search_fields = (
        "id",
        "patient__name",
        "user__email",
        "venue__name",
    )

    autocomplete_fields = (
        "user",
        "patient",
        "venue",
        "venue_package",
    )

    readonly_fields = (
        "venue_cost",
        "services_cost",
        "subtotal",
        "final_amount",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "user",
                "patient",
                "status",
                "continue_booking",
            )
        }),
        ("Venue Booking", {
            "fields": (
                "venue",
                "venue_package",
                "start_datetime",
                "end_datetime",
            )
        }),
        ("Pricing", {
            "fields": (
                "venue_cost",
                "services_cost",
                "subtotal",
                "discount",
                "final_amount",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    inlines = [BookingServiceInline]

    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    actions = ["recalculate_selected_bookings"]
    
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, BookingService):
                instance.patient = form.instance.patient
                instance.user = form.instance.user
                instance.booking = form.instance
                instance.save()

        formset.save_m2m()
    # -------------------------
    # Custom Display Helpers
    # -------------------------
    def status_badge(self, obj):
        color_map = {
            "DRAFT": "gray",
            "BOOKED": "blue",
            "IN_PROGRESS": "orange",
            "FULFILLED": "green",
            "CANCELLED": "red",
            "DELAYED": "purple",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            '<b style="color:{};">{}</b>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def booking_state(self, obj):
        now = timezone.now()
        if obj.is_ongoing:
            return format_html('<span style="color:orange;">Ongoing</span>')
        if obj.is_upcoming:
            return format_html('<span style="color:blue;">Upcoming</span>')
        return format_html('<span style="color:green;">Completed</span>')
    booking_state.short_description = "State"

    # -------------------------
    # Admin Actions
    # -------------------------
    @admin.action(description="Recalculate totals for selected bookings")
    def recalculate_selected_bookings(self, request, queryset):
        for booking in queryset:
            booking.save()
        self.message_user(request, "Selected bookings recalculated successfully.")


# -------------------------
# BookingService Admin
# -------------------------
@admin.register(BookingService)
class BookingServiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "service",
        "booking",
        "patient",
        "status",
        "start_datetime",
        "end_datetime",
        "service_total_price",
        "created_at",
    )

    list_filter = (
        "status",
        "service",
        "created_at",
    )

    search_fields = (
        "service__name",
        "patient__name",
        "booking__id",
    )

    autocomplete_fields = (
        "booking",
        "service",
        "service_package",
        "patient",
        "user",
    )

    readonly_fields = (
        "service_total_price",
        "created_at",
        "updated_at",
    )

    ordering = ("start_datetime",)

@admin.register(InvoiceTransaction)
class InvoiceTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice_for",
        "booking",
        "transaction_type",
        "status_colored",
        "total_bill_amount",
        "paid_amount",
        "remain_amount",
        "payment_method",
        "due_date",
        "created_at",
    )

    list_filter = (
        "invoice_for",
        "transaction_type",
        "status",
        "payment_method",
        "created_at",
    )

    search_fields = (
        "id",
        "booking__id",
        "reference_id",
        "remarks",
        "notes",
    )

    readonly_fields = (
        "total_bill_amount",
        "remain_amount",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "booking",
        "service_bookings",
        "created_by",
    )

    filter_horizontal = ("service_bookings",)

    fieldsets = (
        (
            "Invoice Scope",
            {
                "fields": (
                    "booking",
                    "invoice_for",
                    "service_bookings",
                )
            },
        ),
        (
            "Billing",
            {
                "fields": (
                    "tax",
                    "total_bill_amount",
                )
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "transaction_type",
                    "payment_method",
                    "paid_amount",
                    "remain_amount",
                    "reference_id",
                    "status",
                )
            },
        ),
        (
            "Additional Info",
            {
                "fields": (
                    "remarks",
                    "notes",
                    "due_date",
                )
            },
        ),
        (
            "Meta",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    ordering = ("-created_at",)

    # --------------------------------------------------
    # Custom display helpers
    # --------------------------------------------------

    @admin.display(description="Status")
    def status_colored(self, obj):
        color_map = {
            obj.PaymentStatus.PAID: "green",
            obj.PaymentStatus.PARTIALLY_PAID: "orange",
            obj.PaymentStatus.PENDING: "red",
            obj.PaymentStatus.CANCELLED: "gray",
        }
        color = color_map.get(obj.status, "black")
        return format_html(
            '<b style="color:{};">{}</b>',
            color,
            obj.get_status_display(),
        )
