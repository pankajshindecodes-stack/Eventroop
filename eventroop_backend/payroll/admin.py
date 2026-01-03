from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q
from .models import SalaryStructure, SalaryTransaction



# ------------------------------------------
# Custom Filters
# ------------------------------------------
class MonthFilter(admin.SimpleListFilter):
    title = "Month"
    parameter_name = "month"

    def lookups(self, request, model_admin):
        return [(i, i) for i in range(1, 13)]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(effective_from__month=self.value())
        return queryset


class YearFilter(admin.SimpleListFilter):
    title = "Year"
    parameter_name = "year"

    def lookups(self, request, model_admin):
        years = SalaryStructure.objects.values_list(
            "effective_from__year", flat=True
        ).distinct()
        return [(y, y) for y in years if y]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(effective_from__year=self.value())
        return queryset


class UserFilter(admin.SimpleListFilter):
    title = "User"
    parameter_name = "user"

    def lookups(self, request, model_admin):
        users = (
            SalaryStructure.objects.values_list("user__id", "user__first_name", "user__last_name")
            .distinct()
            .order_by("user__first_name", "user__last_name")
        )
        return [
            (user_id, f"{first_name} {last_name}".strip())
            for user_id, first_name, last_name in users
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__id=self.value())
        return queryset

@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "salary_type",
        "change_type",
        "amount",
        "final_salary",
        "effective_from",
        "created_at",
    )

    list_filter = (
        MonthFilter,
        YearFilter,
        UserFilter,
        "salary_type",
        "change_type",
        "effective_from",
        "created_at",
    )

    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    date_hierarchy = "effective_from"

    readonly_fields = (
        "final_salary",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Employee Information", {
            "fields": ("user",)
        }),
        ("Salary Details", {
            "fields": (
                "salary_type",
                "change_type",
                "amount",
                "final_salary",
            )
        }),
        ("Effective Period", {
            "fields": ("effective_from",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user")
    from django.contrib import admin


@admin.register(SalaryTransaction)
class SalaryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_id",
        "user",
        "total_payable_amount",
        "paid_amount",
        "remaining_payment",
        "status",
        "payment_method",
        "payment_period_start",
        "payment_period_end",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_method",
        "payment_period_start",
    )

    search_fields = (
        "transaction_id",
        "user__email",
        "user__first_name",
        "user__last_name",
        "payment_reference",
    )

    readonly_fields = (
        "transaction_id",
        "remaining_payment",
        "created_at",
        "updated_at",
        "processed_at",
    )

    ordering = ("-created_at",)

    fieldsets = (
        ("Transaction Info", {
            "fields": (
                "transaction_id",
                "status",
                "payment_method",
                "payment_reference",
                "note",
            )
        }),
        ("Users", {
            "fields": ("user",)
        }),
        ("Payment Details", {
            "fields": (
                "total_payable_amount",
                "paid_amount",
                "remaining_payment",
                "daily_rate",
            )
        }),
        ("Salary Period", {
            "fields": (
                "payment_period_start",
                "payment_period_end",
            )
        }),
        ("Timestamps", {
            "fields": (
                "processed_at",
                "created_at",
                "updated_at",
            )
        }),
    )
