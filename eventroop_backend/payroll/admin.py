from django.contrib import admin
from django.utils.html import format_html
from .models import SalaryStructure


@admin.register(SalaryStructure)
class SalaryStructureAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "salary_type",
        "get_rate",
        "total_salary",
        "updated_at",
    )
    list_filter = ("salary_type", "updated_at", "user__user_type")
    search_fields = ("user__first_name", "user__last_name", "user__email")
    readonly_fields = ("updated_at", "calculate_salary_display")
    
    fieldsets = (
        ("User Information", {
            "fields": ("user",)
        }),
        ("Salary Type & Rates", {
            "fields": (
                "salary_type",
                "hour_rate",
                "daily_rate",
                "weekly_rate",
                "fortnight_rate",
                "monthly_rate",
            ),
            "description": "Set the rate based on the selected salary type."
        }),
        ("Total Salary", {
            "fields": ("total_salary",)
        }),
        ("Metadata", {
            "fields": ("updated_at",),
            "classes": ("collapse",)
        }),
    )

    def get_rate(self, obj):
        """Display the current rate based on salary type."""
        rates = {
            "HOURLY": obj.hour_rate,
            "DAILY": obj.daily_rate,
            "WEEKLY": obj.weekly_rate,
            "FORTNIGHTLY": obj.fortnight_rate,
            "MONTHLY": obj.monthly_rate,
        }
        rate = rates.get(obj.salary_type, 0)
        return f"${rate:,.2f}" if rate else "—"
    
    get_rate.short_description = "Current Rate"

    def calculate_salary_display(self, obj):
        """Display salary calculation info (read-only)."""
        if not obj.pk:
            return "—"
        
        attendance = getattr(obj.user, "total_attendance", None)
        if not attendance:
            return format_html(
                '<span style="color: red;">No attendance record found</span>'
            )
        
        salary = obj.calculate_salary(attendance)
        return format_html(
            '<strong style="color: green;">${:,.2f}</strong>',
            salary
        )
    
    calculate_salary_display.short_description = "Calculated Salary"

    def get_readonly_fields(self, request, obj=None):
        """Make user field read-only when editing existing record."""
        if obj:
            return self.readonly_fields + ("user",)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        """Save the model and log changes."""
        super().save_model(request, obj, form, change)
