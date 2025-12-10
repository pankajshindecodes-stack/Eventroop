from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import Attendance, AttendanceStatus,TotalAttendance


# ---------------------------------------------------------
#                 ATTENDANCE STATUS ADMIN
# ---------------------------------------------------------
@admin.register(AttendanceStatus)
class AttendanceStatusAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "owner", "is_active", "get_status_badge")
    list_filter = ("is_active", "owner")
    search_fields = ("label", "code")
    autocomplete_fields = ("owner",)
    
    fieldsets = (
        ("Status Information", {
            "fields": ("label", "code")
        }),
        ("Ownership & Visibility", {
            "fields": ("owner", "is_active")
        }),
    )

    def get_status_badge(self, obj):
        """Display active/inactive status with color coding."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; '
                'border-radius: 3px; font-weight: bold;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">Inactive</span>'
        )
    
    get_status_badge.short_description = "Status"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Owners see only their own statuses
        return qs.filter(owner=request.user)

    def save_model(self, request, obj, form, change):
        if not obj.owner and not request.user.is_superuser:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        """Only allow superuser to delete status."""
        if obj and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)


# ---------------------------------------------------------
#                   ATTENDANCE ADMIN
# ---------------------------------------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "get_date_display",
        "status",
        "get_status_color",
        "created_at",
    )
    list_filter = ("status", "date", "user__user_type", "created_at")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    date_hierarchy = "date"
    
    autocomplete_fields = ("user", "status")
    readonly_fields = ("created_at", "updated_at", "get_attendance_info")
    
    fieldsets = (
        ("Attendance Information", {
            "fields": ("user", "date", "status")
        }),
        ("Additional Info", {
            "fields": ("get_attendance_info",),
            "classes": ("wide",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    actions = ["mark_present", "mark_absent", "mark_leave"]

    def get_date_display(self, obj):
        """Display date in a user-friendly format."""
        return obj.date.strftime("%d %b %Y")
    
    get_date_display.short_description = "Date"
    get_date_display.admin_order_field = "date"

    def get_status_color(self, obj):
        """Display status with color coding based on common status codes."""
        status_colors = {
            "P": ("#28a745", "Present"),
            "A": ("#dc3545", "Absent"),
            "L": ("#ffc107", "Leave"),
            "LH": ("#17a2b8", "Half Day"),
            "WFH": ("#007bff", "WFH"),
        }
        
        color, label = status_colors.get(
            obj.status.code,
            ("#6c757d", obj.status.label)
        )
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.status.label
        )
    
    get_status_color.short_description = "Status"
    get_status_color.admin_order_field = "status"

    def get_attendance_info(self, obj):
        """Display additional attendance information."""
        if not obj.pk:
            return "—"
        
        info = f"""
        <strong>User:</strong> {obj.user.get_full_name()}<br>
        <strong>Email:</strong> {obj.user.email}<br>
        <strong>User Type:</strong> {obj.user.get_user_type_display()}<br>
        <strong>Status:</strong> {obj.status.label} ({obj.status.code})
        """
        return format_html(info)
    
    get_attendance_info.short_description = "Attendance Details"

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superuser sees everything
        if request.user.is_superuser:
            return qs

        # Owner sees: managers + line managers + staff under them
        if request.user.user_type == "VSRE_OWNER":
            return qs.filter(user__hierarchy__owner=request.user)

        # Manager sees staff under them + their own
        if request.user.user_type == "VSRE_MANAGER":
            return qs.filter(
                Q(user=request.user) | 
                Q(user__hierarchy__manager=request.user)
            )

        # Staff see only their own attendance
        return qs.filter(user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            if request.user.is_superuser:
                pass
            elif request.user.user_type == "VSRE_OWNER":
                kwargs["queryset"] = (
                    kwargs["queryset"]
                    .filter(hierarchy__owner=request.user)
                )
            elif request.user.user_type == "VSRE_MANAGER":
                # Manager sees staff under them + themselves
                kwargs["queryset"] = (
                    kwargs["queryset"]
                    .filter(
                        Q(id=request.user.id) |
                        Q(hierarchy__manager=request.user)
                    )
                )
            else:
                # Staff: only themselves
                kwargs["queryset"] = kwargs["queryset"].filter(id=request.user.id)

        if db_field.name == "status":
            if request.user.is_superuser:
                pass
            else:
                kwargs["queryset"] = kwargs["queryset"].filter(
                    Q(owner=request.user) | Q(is_active=True)
                )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        """Restrict who can add attendance."""
        # Superuser, owner, and managers can add
        if request.user.is_superuser:
            return True
        if request.user.user_type in ["VSRE_OWNER", "VSRE_MANAGER"]:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Restrict who can delete attendance."""
        if request.user.is_superuser:
            return True
        # Only managers/owners of the user can delete
        if obj and request.user.user_type in ["VSRE_OWNER", "VSRE_MANAGER"]:
            return True
        return False

    # ----- ACTIONS -----
    
    def mark_present(self, request, queryset):
        """Bulk action to mark selected records as Present."""
        try:
            status = AttendanceStatus.objects.get(code="P")
            updated = queryset.update(status=status)
            self.message_user(
                request,
                f"{updated} attendance record(s) marked as Present."
            )
        except AttendanceStatus.DoesNotExist:
            self.message_user(
                request,
                "Status 'Present' not found. Please create it first.",
                level="error"
            )
    
    mark_present.short_description = "Mark selected as Present"

    def mark_absent(self, request, queryset):
        """Bulk action to mark selected records as Absent."""
        try:
            status = AttendanceStatus.objects.get(code="A")
            updated = queryset.update(status=status)
            self.message_user(
                request,
                f"{updated} attendance record(s) marked as Absent."
            )
        except AttendanceStatus.DoesNotExist:
            self.message_user(
                request,
                "Status 'Absent' not found. Please create it first.",
                level="error"
            )
    
    mark_absent.short_description = "Mark selected as Absent"

    def mark_leave(self, request, queryset):
        """Bulk action to mark selected records as Leave."""
        try:
            status = AttendanceStatus.objects.get(code="L")
            updated = queryset.update(status=status)
            self.message_user(
                request,
                f"{updated} attendance record(s) marked as Leave."
            )
        except AttendanceStatus.DoesNotExist:
            self.message_user(
                request,
                "Status 'Leave' not found. Please create it first.",
                level="error"
            )
    
    mark_leave.short_description = "Mark selected as Leave"

# attendance/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from .models import TotalAttendance


@admin.register(TotalAttendance)
class TotalAttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "get_daily_hours_display",
        "get_weekly_hours_display",
        "get_fortnightly_hours_display",
        "get_monthly_hours_display",
        "updated_at",
    )
    list_filter = ("updated_at", "user__user_type", "created_at")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    
    readonly_fields = (
        "user",
        "total_hours_day",
        "total_hours_week",
        "total_hours_fortnight",
        "total_hours_month",
        "created_at",
        "updated_at",
        "get_attendance_summary",
        "get_hours_chart",
    )
    
    fieldsets = (
        ("User Information", {
            "fields": ("user",)
        }),
        ("Attendance Summary", {
            "fields": ("get_attendance_summary",),
            "classes": ("wide",)
        }),
        ("Hours Breakdown", {
            "fields": (
                "total_hours_day",
                "total_hours_week",
                "total_hours_fortnight",
                "total_hours_month",
            ),
            "description": "These fields are automatically updated from attendance records via signals."
        }),
        ("Hours Visualization", {
            "fields": ("get_hours_chart",),
            "classes": ("wide",)
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def get_daily_hours_display(self, obj):
        """Display daily hours with color coding."""
        hours = float(obj.total_hours_day)
        
        if hours == 0:
            color = "#dc3545"  # red
            status = "No hours"
        elif hours < 4:
            color = "#ffc107"  # yellow/orange
            status = f"{hours}h"
        else:
            color = "#28a745"  # green
            status = f"{hours}h"
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">{}</span>',
            color,
            status
        )
    
    get_daily_hours_display.short_description = "Daily Hours"
    get_daily_hours_display.admin_order_field = "total_hours_day"

    def get_weekly_hours_display(self, obj):
        """Display weekly hours with color coding."""
        hours = float(obj.total_hours_week)
        expected = 40  # Standard 40-hour work week
        
        if hours == 0:
            color = "#dc3545"  # red
            status = "No hours"
        elif hours < expected * 0.8:  # Less than 80% of expected
            color = "#ffc107"  # yellow/orange
            status = f"{hours}h"
        else:
            color = "#28a745"  # green
            status = f"{hours}h"
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">{}</span>',
            color,
            status
        )
    
    get_weekly_hours_display.short_description = "Weekly Hours"
    get_weekly_hours_display.admin_order_field = "total_hours_week"

    def get_fortnightly_hours_display(self, obj):
        """Display fortnightly hours with color coding."""
        hours = float(obj.total_hours_fortnight)
        expected = 80  # Standard 80-hour work fortnight
        
        if hours == 0:
            color = "#dc3545"  # red
            status = "No hours"
        elif hours < expected * 0.8:
            color = "#ffc107"
            status = f"{hours}h"
        else:
            color = "#28a745"
            status = f"{hours}h"
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">{}</span>',
            color,
            status
        )
    
    get_fortnightly_hours_display.short_description = "Fortnightly Hours"
    get_fortnightly_hours_display.admin_order_field = "total_hours_fortnight"

    def get_monthly_hours_display(self, obj):
        """Display monthly hours with color coding."""
        hours = float(obj.total_hours_month)
        expected = 160  # Standard 160-hour work month
        
        if hours == 0:
            color = "#dc3545"  # red
            status = "No hours"
        elif hours < expected * 0.8:
            color = "#ffc107"
            status = f"{hours}h"
        else:
            color = "#28a745"
            status = f"{hours}h"
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 5px 10px; '
            'border-radius: 4px; font-weight: bold; display: inline-block;">{}</span>',
            color,
            status
        )
    
    get_monthly_hours_display.short_description = "Monthly Hours"
    get_monthly_hours_display.admin_order_field = "total_hours_month"

    def get_attendance_summary(self, obj):
        """Display a comprehensive attendance summary."""
        if not obj.pk:
            return "—"
        
        daily = float(obj.total_hours_day)
        weekly = float(obj.total_hours_week)
        fortnightly = float(obj.total_hours_fortnight)
        monthly = float(obj.total_hours_month)
        
        summary = f"""
        <div style="font-size: 14px; line-height: 1.8;">
            <strong style="color: #333;">User:</strong> {obj.user.get_full_name()}<br>
            <strong style="color: #333;">Email:</strong> {obj.user.email}<br>
            <strong style="color: #333;">User Type:</strong> {obj.user.get_user_type_display()}<br>
            <hr style="margin: 10px 0;">
            <strong style="color: #333;">Hours Summary:</strong><br>
            <div style="margin-left: 20px;">
                • Today: <strong>{daily} hours</strong><br>
                • This Week: <strong>{weekly} hours</strong><br>
                • This Fortnight: <strong>{fortnightly} hours</strong><br>
                • This Month: <strong>{monthly} hours</strong>
            </div>
        </div>
        """
        return format_html(summary)
    
    get_attendance_summary.short_description = "Attendance Summary"

    def get_hours_chart(self, obj):
        """Display a simple ASCII-style bar chart of hours."""
        if not obj.pk:
            return "—"
        
        daily = float(obj.total_hours_day)
        weekly = float(obj.total_hours_week)
        fortnightly = float(obj.total_hours_fortnight)
        monthly = float(obj.total_hours_month)
        
        # Normalize to percentages for visualization
        max_hours = max(daily, weekly, fortnightly, monthly, 1)
        
        daily_pct = int((daily / max_hours) * 100) if max_hours > 0 else 0
        weekly_pct = int((weekly / max_hours) * 100) if max_hours > 0 else 0
        fortnight_pct = int((fortnightly / max_hours) * 100) if max_hours > 0 else 0
        monthly_pct = int((monthly / max_hours) * 100) if max_hours > 0 else 0
        
        chart = f"""
        <div style="font-family: monospace; font-size: 12px; line-height: 2;">
            <div>Daily ({daily}h): 
                <div style="background-color: #e9ecef; display: inline-block; width: 300px; height: 20px; border-radius: 3px; overflow: hidden;">
                    <div style="background-color: #007bff; width: {min(daily_pct, 100)}%; height: 100%;"></div>
                </div>
            </div>
            <div>Weekly ({weekly}h): 
                <div style="background-color: #e9ecef; display: inline-block; width: 300px; height: 20px; border-radius: 3px; overflow: hidden;">
                    <div style="background-color: #28a745; width: {min(weekly_pct, 100)}%; height: 100%;"></div>
                </div>
            </div>
            <div>Fortnightly ({fortnightly}h): 
                <div style="background-color: #e9ecef; display: inline-block; width: 300px; height: 20px; border-radius: 3px; overflow: hidden;">
                    <div style="background-color: #ffc107; width: {min(fortnight_pct, 100)}%; height: 100%;"></div>
                </div>
            </div>
            <div>Monthly ({monthly}h): 
                <div style="background-color: #e9ecef; display: inline-block; width: 300px; height: 20px; border-radius: 3px; overflow: hidden;">
                    <div style="background-color: #17a2b8; width: {min(monthly_pct, 100)}%; height: 100%;"></div>
                </div>
            </div>
        </div>
        """
        return format_html(chart)
    
    get_hours_chart.short_description = "Hours Visualization"

    def get_queryset(self, request):
        """Filter queryset based on user hierarchy."""
        qs = super().get_queryset(request)
        
        # Superuser sees everything
        if request.user.is_superuser:
            return qs
        
        # Owner sees all staff under them
        if request.user.user_type == "VSRE_OWNER":
            return qs.filter(user__hierarchy__owner=request.user)
        
        # Manager sees staff under them + themselves
        if request.user.user_type == "VSRE_MANAGER":
            return qs.filter(
                Q(user=request.user) | 
                Q(user__hierarchy__manager=request.user)
            )
        
        # Staff see only their own record
        return qs.filter(user=request.user)

    def has_add_permission(self, request):
        """Prevent manual creation of TotalAttendance records."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of TotalAttendance records."""
        return False

    def has_change_permission(self, request, obj=None):
        """Allow viewing but restrict editing."""
        # Superusers can view all
        if request.user.is_superuser:
            return True
        
        # Check hierarchy permissions for viewing
        if obj:
            if request.user.user_type == "VSRE_OWNER":
                return obj.user.hierarchy.owner == request.user
            elif request.user.user_type == "VSRE_MANAGER":
                return (obj.user == request.user or 
                        obj.user.hierarchy.manager == request.user)
            else:
                return obj.user == request.user
        
        return True

    def save_model(self, request, obj, form, change):
        """Prevent direct editing (should be updated via signals)."""
        pass