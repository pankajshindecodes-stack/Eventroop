# admin.py
from django.contrib import admin
from django import forms
from django.utils import timezone
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError

from .models import CustomUser, UserHierarchy, PricingModel, UserPlan


# -------------------------------------------------------------------
#                         USER FORMS
# -------------------------------------------------------------------
class CustomUserCreationForm(forms.ModelForm):
    """Form for creating new users in admin with password confirmation."""

    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm Password", widget=forms.PasswordInput)

    class Meta:
        model = CustomUser
        fields = (
            "profile_pic",
            "email",
            "mobile_number",
            "first_name",
            "middle_name",
            "last_name",
            "gender",
            "user_type",
            "city",
            "category",
        )

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """Form for updating users in admin. Password is read-only hash."""

    password = ReadOnlyPasswordHashField()

    class Meta:
        model = CustomUser
        fields = "__all__"


# -------------------------------------------------------------------
#                         INLINE ADMIN: USER PLAN
# -------------------------------------------------------------------
class UserPlanInline(admin.TabularInline):
    model = UserPlan
    extra = 0
    readonly_fields = ("end_date", "is_active")
    fields = ("plan", "start_date", "end_date", "is_active")
    show_change_link = True


# -------------------------------------------------------------------
#                         USER ADMIN
# -------------------------------------------------------------------
@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Custom admin for the main user model."""

    form = CustomUserChangeForm
    add_form = CustomUserCreationForm

    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "mobile_number",
        "user_type",
        "city",
        "is_active",
        "is_staff",
        "created_by"
    )
    list_filter = ("user_type", "is_active", "is_staff", "city")
    search_fields = (
        "email",
        "first_name",
        "last_name",
        "mobile_number",
        "employee_id",
    )
    ordering = ("email",)
    readonly_fields = ("date_joined",)

    fieldsets = (
        ("Account Info", {"fields": ("email", "password")}),
        (
            "Personal Details",
            {
                "fields": (
                    "profile_pic",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "gender",
                    "mobile_number",
                    "emergency_contact",
                    "address",
                    "city",
                    "category",
                )
            },
        ),
        (
            "Role & Permissions",
            {
                "fields": (
                    "user_type",
                    "created_by",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Additional Data",
            {
                "fields": (
                    "employee_id",
                    "skills",
                    "order_types",
                    "target_percent",
                    "qc_required",
                )
            },
        ),
        ("Important Dates", {"fields": ("date_joined", "last_working_day")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "mobile_number",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "gender",
                    "city",
                    "user_type",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    inlines = (UserPlanInline,)
    actions = ["activate_users", "deactivate_users"]

    def save_model(self, request, obj, form, change):
        """Ensure essential fields are filled and user is saved."""
        if not obj.email:
            raise ValidationError("Email is required.")
        if not obj.mobile_number:
            raise ValidationError("Mobile number is required.")
        super().save_model(request, obj, form, change)

    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"{count} user(s) activated.")
    activate_users.short_description = "Activate selected users"

    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} user(s) deactivated.")
    deactivate_users.short_description = "Deactivate selected users"


# -------------------------------------------------------------------
#                         USER HIERARCHY ADMIN
# -------------------------------------------------------------------
@admin.register(UserHierarchy)
class UserHierarchyAdmin(admin.ModelAdmin):
    """Manage reporting relationships between users."""

    list_display = ("id","user", "parent", "owner", "level", "band","department")
    list_filter = ("owner", "parent", "level","band","department")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "owner__email",
        "parent__email",
    )
    raw_id_fields = ("user", "owner", "parent")
    readonly_fields = ("level",)


# -------------------------------------------------------------------
#                         PRICING MODEL ADMIN
# -------------------------------------------------------------------
@admin.register(PricingModel)
class PricingModelAdmin(admin.ModelAdmin):
    """Manage pricing plans and limits."""

    list_display = (
        "name",
        "plan_type",
        "price",
        "duration_days",
        "max_venues",
        "max_services",
        "max_resources",
        "is_active",
        "created_by",
        "created_at",
    )
    list_filter = ("plan_type", "is_active", "created_by")
    search_fields = ("name", "description", "created_by__email")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "description",
                    "plan_type",
                    "price",
                    "duration_days",
                )
            },
        ),
        (
            "Usage Limits",
            {"fields": ("max_venues", "max_services", "max_resources")},
        ),
        (
            "Meta",
            {"fields": ("is_active", "created_by", "created_at", "updated_at")},
        ),
    )

    def save_model(self, request, obj, form, change):
        obj.clean()
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# -------------------------------------------------------------------
#                         USER PLAN ADMIN
# -------------------------------------------------------------------
@admin.register(UserPlan)
class UserPlanAdmin(admin.ModelAdmin):
    """Manage active and expired user plans."""

    list_display = ("user", "plan", "start_date", "end_date", "is_active")
    list_filter = ("plan__plan_type", "is_active", "plan")
    search_fields = ("user__email", "plan__name")
    readonly_fields = ("end_date", "is_active")
    actions = ["expire_plans", "activate_plans"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("user", "plan")

    def save_model(self, request, obj, form, change):
        obj.clean()
        super().save_model(request, obj, form, change)

    def expire_plans(self, request, queryset):
        count = 0
        for plan in queryset:
            plan.is_active = False
            plan.end_date = timezone.now()
            plan.save()
            count += 1
        self.message_user(request, f"{count} plan(s) expired.")
    expire_plans.short_description = "Expire selected plans"

    def activate_plans(self, request, queryset):
        count = 0
        for plan in queryset:
            plan.is_active = True
            if (
                plan.plan.plan_type == "SUBSCRIPTION"
                and (not plan.end_date or plan.end_date < timezone.now())
            ):
                plan.end_date = plan.start_date + timezone.timedelta(
                    days=plan.plan.duration_days
                )
            plan.save()
            count += 1
        self.message_user(request, f"{count} plan(s) activated.")
    activate_plans.short_description = "Activate selected plans"
