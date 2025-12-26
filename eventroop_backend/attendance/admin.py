from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.utils.timezone import now

from .models import AttendanceStatus, Attendance


# ------------------------------------------
# Attendance Status Admin
# ------------------------------------------
@admin.register(AttendanceStatus)
class AttendanceStatusAdmin(admin.ModelAdmin):
    list_display = (
        "owner",
        "label",
        "code",
        "is_active",   # must be here for list_editable
    )

    list_editable = ("is_active",)  # allowed now
    list_filter = ("owner", "is_active")
    search_fields = ("label", "code", "owner__email")
    ordering = ("owner", "label")
    list_per_page = 25
 


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
            return queryset.filter(date__month=self.value())
        return queryset


class YearFilter(admin.SimpleListFilter):
    title = "Year"
    parameter_name = "year"

    def lookups(self, request, model_admin):
        years = queryset_years = Attendance.objects.values_list(
            "date__year", flat=True
        ).distinct()
        return [(y, y) for y in years if y]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(date__year=self.value())
        return queryset


# ------------------------------------------
# Attendance Admin
# ------------------------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "status_badge",
        "formatted_duration",
        "created_at",
    )

    list_filter = (
        "status",
        MonthFilter,
        YearFilter,
    )

    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    ordering = ("-date",)
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)
    list_select_related = ("user", "status")
    list_per_page = 30
    actions = (
        "mark_present",
        "mark_absent",
    )

    # ------------------------------------------
    # Display helpers
    # ------------------------------------------
    @admin.display(description="Status")
    def status_badge(self, obj):
        color_map = {
            "P": "green",
            "A": "red",
            "H": "orange",
            "L": "blue",
        }
        color = color_map.get(obj.status.code, "gray")
        return format_html(
            '<span style="color:white; background:{}; padding:4px 8px; border-radius:6px;">{}</span>',
            color,
            obj.status.label,
        )

    @admin.display(description="Duration (hrs)")
    def formatted_duration(self, obj):
        if obj.duration:
            hours = obj.duration.total_seconds() / 3600
            return f"{hours:.2f}"
        return "-"

    # ------------------------------------------
    # Bulk Actions
    # ------------------------------------------
    @admin.action(description="Mark selected as Present")
    def mark_present(self, request, queryset):
        present_status = AttendanceStatus.objects.filter(
            code="P", is_active=True
        ).first()
        if present_status:
            queryset.update(status=present_status)

    @admin.action(description="Mark selected as Absent")
    def mark_absent(self, request, queryset):
        absent_status = AttendanceStatus.objects.filter(
            code="A", is_active=True
        ).first()
        if absent_status:
            queryset.update(status=absent_status)

    # ------------------------------------------
    # Permissions
    # ------------------------------------------
    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletes
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "status")
