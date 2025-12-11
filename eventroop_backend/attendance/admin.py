from django.contrib import admin
from .models import AttendanceStatus, Attendance, TotalAttendance


# ------------------------------------------
# Attendance Status Admin
# ------------------------------------------
@admin.register(AttendanceStatus)
class AttendanceStatusAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "is_active")
    search_fields = ("label", "code")
    list_filter = ("is_active",)
    ordering = ("label",)


# ------------------------------------------
# Attendance Admin
# ------------------------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "status",
        "formatted_duration",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "date")
    search_fields = ("user__first_name", "user__last_name", "user__email")
    ordering = ("-date",)
    readonly_fields = ("created_at", "updated_at")

    def formatted_duration(self, obj):
        if obj.duration:
            hours = obj.duration.total_seconds() / 3600
            return f"{hours:.2f} Hours"
        return "-"
    formatted_duration.short_description = "Duration (hrs)"


# ------------------------------------------
# Total Attendance Admin
# ------------------------------------------
@admin.register(TotalAttendance)
class TotalAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "present_days",
        "absent_days",
        "half_day_count",
        "paid_leave_days",
        "payable_days",
        "total_payable_hours",
        "updated_at",
    )
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    ordering = ("user__first_name",)
    readonly_fields = ("created_at", "updated_at")

    list_filter = ("updated_at",)
