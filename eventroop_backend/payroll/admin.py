from django.contrib import admin
from .models import SalaryStructure, PayRollPayment


# ---------------------------------------------
# Salary Structure Admin
# ---------------------------------------------
@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "salary_type",
        "rate",
        "total_salary",
        "advance_amount",
        "is_increment",
        "created_at",
    )

    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    list_filter = (
        "salary_type",
        "is_increment",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Employee", {
            "fields": ("user",)
        }),
        ("Salary Info", {
            "fields": ("salary_type", "rate", "total_salary", "advance_amount", "is_increment")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        })
    )


# ---------------------------------------------
# PayRollPayment Admin
# ---------------------------------------------
@admin.register(PayRollPayment)
class PayRollPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "receiver",
        "payment_type",
        "amount",
        "status",
        "created_at",
        "updated_at",
    )

    search_fields = (
        "receiver__first_name",
        "receiver__last_name",
        "receiver__email",
        "note",
    )

    list_filter = (
        "payment_type",
        "status",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Payment Info", {
            "fields": ("receiver", "payment_type", "amount", "status")
        }),
        ("Additional Details", {
            "fields": ("note", "attachment")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    # Show file link nicely in admin
    def attachment_link(self, obj):
        if obj.attachment:
            return f"<a href='{obj.attachment.url}' target='_blank'>View Receipt</a>"
        return "-"
    attachment_link.allow_tags = True
    attachment_link.short_description = "Receipt"


