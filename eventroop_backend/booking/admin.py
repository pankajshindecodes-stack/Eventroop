from django.contrib import admin
from .models import (
    Location,
    Package,
    Patient,
    PrimaryOrder,
    SecondaryOrder,
    TernaryOrder,
    TotalInvoice,
    Payment,
)

# Location
@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("building_name", "city", "state", "location_type", "user")
    list_filter = ("location_type", "city", "state")
    search_fields = ("building_name", "city", "state", "postal_code")
    autocomplete_fields = ("user",)

# Package
@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "package_type", "period", "price", "is_active", "created_at")
    list_filter = ("package_type", "period", "is_active")
    search_fields = ("name", "owner__email")
    autocomplete_fields = ("owner",)
    readonly_fields = ("created_at", "updated_at")

# Patient
@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("patient_id", "first_name", "last_name", "phone", "gender", "registration_date")
    list_filter = ("gender", "blood_group", "registration_date")
    search_fields = ("patient_id", "first_name", "last_name", "phone", "email")
    autocomplete_fields = ("registered_by",)
    readonly_fields = ("patient_id", "registration_date", "updated_at")
    date_hierarchy = "registration_date"

# Ternary Inline (inside Secondary)
class TernaryOrderInline(admin.TabularInline):
    model = TernaryOrder
    extra = 0
    readonly_fields = ("order_id", "subtotal", "created_at", "updated_at")
    autocomplete_fields = ("service", "package")

# Secondary Inline (inside Primary)
class SecondaryOrderInline(admin.TabularInline):
    model = SecondaryOrder
    extra = 0
    readonly_fields = ("order_id", "subtotal", "created_at", "updated_at")
    show_change_link = True

# PrimaryOrder
@admin.register(PrimaryOrder)
class PrimaryOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "booking_entity",
        "patient",
        "package",
        "start_datetime",
        "end_datetime",
        "status",
        "total_bill",
        "created_at",
    )
    list_filter = ("booking_entity", "booking_type", "status", "created_at")
    search_fields = ("order_id", "patient__first_name", "patient__last_name")
    autocomplete_fields = ("user", "patient", "venue", "service", "package")
    readonly_fields = ("order_id", "total_bill", "created_at", "updated_at")
    date_hierarchy = "created_at"
    inlines = [SecondaryOrderInline]

# SecondaryOrder
@admin.register(SecondaryOrder)
class SecondaryOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "primary_order",
        "status",
        "subtotal",
    )
    list_filter = ("status",)
    search_fields = ("order_id", "primary_order__order_id")
    readonly_fields = ("order_id", "subtotal", "created_at", "updated_at")
    autocomplete_fields = ("primary_order",)
    inlines = [TernaryOrderInline]

# TernaryOrder
@admin.register(TernaryOrder)
class TernaryOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_id",
        "secondary_order",
        "service",
        "package",
        "status",
        "subtotal",
    )
    list_filter = ("booking_entity", "booking_type", "status")
    search_fields = ("order_id", "secondary_order__order_id")
    readonly_fields = ("order_id", "subtotal", "created_at", "updated_at")
    autocomplete_fields = ("secondary_order", "service", "package")

# Payment Inline (inside Invoice)
class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("created_at",)

# TotalInvoice
@admin.register(TotalInvoice)
class TotalInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "secondary_order",
        "patient",
        "total_amount",
        "paid_amount",
        "remaining_amount",
        "status",
        "issued_date",
    )
    list_filter = ("status", "issued_date")
    search_fields = ("invoice_number", "patient__first_name", "patient__last_name")
    autocomplete_fields = ("secondary_order", "patient", "user")
    readonly_fields = (
        "invoice_number",
        "subtotal",
        "total_amount",
        "remaining_amount",
        "issued_date",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "issued_date"
    inlines = [PaymentInline]

# Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "invoice",
        "patient",
        "amount",
        "method",
        "is_verified",
        "paid_date",
    )
    list_filter = ("method", "is_verified", "paid_date")
    search_fields = ("reference", "invoice__invoice_number")
    autocomplete_fields = ("invoice", "patient")
    readonly_fields = ("reference", "created_at")
    date_hierarchy = "paid_date"