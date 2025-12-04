from django.contrib import admin
from .models import Attendance, AttendanceStatus


# ---------------------------------------------------------
#                 ATTENDANCE STATUS ADMIN
# ---------------------------------------------------------
@admin.register(AttendanceStatus)
class AttendanceStatusAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "owner", "is_active")
    list_filter = ("is_active", "owner")
    search_fields = ("label", "code")
    autocomplete_fields = ("owner",)

    # Optional: restrict queryset per admin user (for multi-owner systems)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Superusers see all
        if request.user.is_superuser:
            return qs
        # Owners see only their own statuses
        return qs.filter(owner=request.user)

    # Auto-assign owner if logged-in user is Owner
    def save_model(self, request, obj, form, change):
        if not obj.owner and not request.user.is_superuser:
            obj.owner = request.user
        super().save_model(request, obj, form, change)


# ---------------------------------------------------------
#                   ATTENDANCE ADMIN
# ---------------------------------------------------------
@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "status", "created_at")
    list_filter = ("status", "date")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    autocomplete_fields = ("user", "status")

    readonly_fields = ("created_at", "updated_at")

    # Show attendance based on hierarchy
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superuser sees everything
        if request.user.is_superuser:
            return qs

        # Owner sees: managers + line managers + staff under him
        if request.user.user_type == "VSRE_OWNER":
            return qs.filter(
                user__hierarchy__owner=request.user
            )

        # Manager / staff see only their own attendance
        return qs.filter(user=request.user)

    # Auto-restrict selection of users based on hierarchy
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            if request.user.is_superuser:
                pass
            elif request.user.user_type == "VSRE_OWNER":
                kwargs["queryset"] = (
                    kwargs["queryset"]
                    .filter(hierarchy__owner=request.user)
                )
            else:
                # Staff/manager: only themselves
                kwargs["queryset"] = kwargs["queryset"].filter(id=request.user.id)

        if db_field.name == "status":
            if request.user.is_superuser:
                pass
            else:
                kwargs["queryset"] = kwargs["queryset"].filter(owner=request.user)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)
