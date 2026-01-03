from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from django.utils.timezone import now
from django.urls import reverse
from .models import AttendanceStatus, Attendance,AttendanceReport


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


class UserFilter(admin.SimpleListFilter):
    title = "User"
    parameter_name = "user"

    def lookups(self, request, model_admin):
        users = (
            Attendance.objects.values_list("user__id", "user__first_name", "user__last_name")
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


# ------------------------------------------
# Attendance Admin
# ------------------------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "date",
        "status_editable",
        "formatted_duration",
        "created_at",
    )

    list_filter = (
        UserFilter,
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

    # ------------------------------------------
    # Display helpers
    # ------------------------------------------
    @admin.display(description="Status")
    def status_editable(self, obj):
        statuses = AttendanceStatus.objects.filter(is_active=True)
        options = "".join(
            [
                f'<option value="{s.id}" {"selected" if obj.status.id == s.id else ""}>{s.label}</option>'
                for s in statuses
            ]
        )
        return format_html(
            '<select data-id="{}" class="status-select" style="padding: 5px; border-radius: 4px;">{}</select>',
            obj.id,
            format_html(options),
        )

    status_editable.short_description = "Status"

    @admin.display(description="Duration (hrs)")
    def formatted_duration(self, obj):
        if obj.duration:
            hours = obj.duration.total_seconds() / 3600
            return f"{hours:.2f}"
        return "-"

    # ------------------------------------------
    # Bulk Actions
    # ------------------------------------------
    def changeform_add_ons(self):
        return """
        <script>
        document.addEventListener('DOMContentLoaded', function() {
            const selects = document.querySelectorAll('.status-select');
            selects.forEach(select => {
                select.addEventListener('change', function() {
                    const attendanceId = this.getAttribute('data-id');
                    const statusId = this.value;
                    const row = this.closest('tr');
                    
                    fetch(`/admin/attendance/attendance/${attendanceId}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
                        },
                        body: JSON.stringify({ status: statusId })
                    })
                    .then(response => {
                        if (response.ok) {
                            row.style.backgroundColor = '#e8f5e9';
                            setTimeout(() => row.style.backgroundColor = '', 1000);
                        } else {
                            alert('Failed to update status');
                            location.reload();
                        }
                    })
                    .catch(err => {
                        console.error('Error:', err);
                        alert('Error updating status');
                    });
                });
            });
        });
        </script>
        """

    class Media:
        js = ('admin/js/status-update.js',)
        css = {'all': ('admin/css/status-update.css',)}

    # ------------------------------------------
    # Permissions
    # ------------------------------------------
    def has_delete_permission(self, request, obj=None):
        # Prevent accidental deletes
        return request.user.is_superuser

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "status")
    list_display = (
        "user",
        "date",
        "status_badge",
        "formatted_duration",
        "created_at",
    )

    list_filter = (
        UserFilter,
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


@admin.register(AttendanceReport)
class AttendanceReportAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = (
        'user', 
        'start_date', 
        'end_date', 
        'total_payable_days', 
        'total_payable_hours', 
    )

    # Fields to filter in the sidebar
    list_filter = (
        'start_date',
        'end_date',
        'created_at',
        'updated_at',
    )

    # Fields searchable via search bar
    search_fields = (
        'user__first_name', 
        'user__last_name', 
        'user__email'
    )

    # Default ordering
    ordering = ('-start_date', '-end_date')

    # Make some fields read-only
    readonly_fields = ('created_at', 'updated_at')

    # Optional: group fields into sections
    fieldsets = (
        ('User & Period', {
            'fields': ('user', 'start_date', 'end_date')
        }),
        ('Attendance Data', {
            'fields': (
                'present_days', 
                'absent_days', 
                'half_day_count', 
                'paid_leave_days',
                'weekly_Offs',
                'unpaid_leaves',
                'total_payable_days',
                'total_payable_hours',
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )