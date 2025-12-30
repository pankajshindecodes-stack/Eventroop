from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import SalaryStructure, SalaryTransaction

@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "salary_type",
        "total_salary",
        "effective_from",
        "is_increment",
        "created_at",
    )
    list_filter = ("user", "salary_type", "is_increment", "effective_from", "created_at")
    search_fields = ("user__first_name", "user__last_name", "user__email")
    date_hierarchy = "effective_from"
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        ("Employee Information", {
            "fields": ("user",)
        }),
        ("Salary Details", {
            "fields": ("salary_type", "base_salary", "total_salary")
        }),
        ("Additional Information", {
            "fields": ("advance_amount", "is_increment")
        }),
        ("Effective Period", {
            "fields": ("effective_from",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user")

@admin.register(SalaryTransaction)
class SalaryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "receiver_name",
        "amount_display",
        "payment_type",
        "status_badge",
        "payment_period_display",
        "processed_at",
    )
    list_filter = (
        "status",
        "payment_type",
        "payment_method",
        "payment_period_start",
        "created_at",
    )
    search_fields = (
        "transaction_id",
        "receiver__first_name",
        "receiver__last_name",
        "receiver__email",
        "payment_reference",
    )
    date_hierarchy = "payment_period_start"
    readonly_fields = (
        "transaction_id",
        "created_at",
        "updated_at",
        "transaction_info",
    )

    fieldsets = (
        ("Transaction Details", {
            "fields": ("transaction_id", "transaction_info")
        }),
        ("Salary Payment", {
            "fields": ("receiver", "payer", "amount", "payment_type")
        }),
        ("Payment Period", {
            "fields": ("payment_period_start", "payment_period_end")
        }),
        ("Payment Method", {
            "fields": ("payment_method", "payment_reference")
        }),
        ("Status & Processing", {
            "fields": ("status", "processed_at", "note")
        }),
        ("Attachments", {
            "fields": ("attachment",),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    actions = ["mark_as_processing", "mark_as_failed", "reset_to_pending"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("receiver", "payer")

    def receiver_name(self, obj):
        return obj.receiver.get_full_name()
    receiver_name.short_description = "Employee"

    def amount_display(self, obj):
        return f"₹ {obj.amount:,.2f}"
    amount_display.short_description = "Amount"

    def status_badge(self, obj):
        status_colors = {
            "PENDING": "#FFA500",
            "PROCESSING": "#3498DB",
            "SUCCESS": "#27AE60",
            "FAILED": "#E74C3C",
            "CANCELLED": "#95A5A6",
        }
        color = status_colors.get(obj.status, "#95A5A6")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def payment_period_display(self, obj):
        return f"{obj.payment_period_start} → {obj.payment_period_end}"
    payment_period_display.short_description = "Period"

    def transaction_info(self, obj):
        info = f"<strong>Transaction ID:</strong> {obj.transaction_id}<br>"
        info += f"<strong>Created:</strong> {obj.created_at}<br>"
        if obj.processed_at:
            info += f"<strong>Processed:</strong> {obj.processed_at}"
        return format_html(info)
    transaction_info.short_description = "Transaction Information"

    def mark_as_processing(self, request, queryset):
        updated = queryset.filter(status="PENDING").update(status="PROCESSING")
        self.message_user(request, f"{updated} transaction(s) marked as processing.")
    mark_as_processing.short_description = "Mark selected as Processing"

    def mark_as_failed(self, request, queryset):
        updated = queryset.exclude(status="SUCCESS").update(status="FAILED")
        self.message_user(request, f"{updated} transaction(s) marked as failed.")
    mark_as_failed.short_description = "Mark selected as Failed"

    def reset_to_pending(self, request, queryset):
        updated = queryset.exclude(status="SUCCESS").update(status="PENDING")
        self.message_user(request, f"{updated} transaction(s) reset to pending.")
    reset_to_pending.short_description = "Reset selected to Pending"