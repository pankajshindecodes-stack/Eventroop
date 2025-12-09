# serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404

from .models import CustomUser, UserHierarchy, PricingModel, UserPlan
from venue_manager.models import Venue,Service,Resource

# ---------------------- Entity mini Serializer ----------------------
class VenueMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "city", "is_active"]
class ServiceMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "city", "is_active"]
class ResourceMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "name", "city", "is_active"]

# ------------------------------------------------------------------
# ---------------------- User Profile Serializer ----------------------
class BaseUserSerializer(serializers.ModelSerializer):
    """Base serializer for all user types with shared profile fields."""

    password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "profile_pic",
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "mobile_number",
            "emergency_contact",
            "user_type",
            "gender",
            "address",
            "city",
            "date_joined",
            "created_by",
            "password",
            "confirm_password"
        ]
        read_only_fields = ["id", "user_type","created_by",'last_working_day']

    # ---------------------- Validation ----------------------
    def validate(self, data):
        password = data.get("password")
        confirm_password = data.get("confirm_password")

        if password or confirm_password:
            if password != confirm_password:
                raise serializers.ValidationError("Passwords do not match.")
        return data

    # ---------------------- Create ----------------------
    def create(self, validated_data):
        request = self.context["request"]
        creator = request.user

        # Remove unwanted fields
        password = validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)

        # Assign creator
        if any((creator.is_owner, creator.is_manager)):
            validated_data["created_by"] = creator

        # Create user
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()

        # ====================================================
        #  HIERARCHY CREATION ONLY FOR OWNER / MANAGER / STAFF
        # ====================================================
        if any((user.is_owner, user.is_manager, user.is_vsre_staff)):
            # Determine owner
            if creator.is_superuser or creator.is_owner or creator.is_manager:
                owner = creator
            else:
                owner = creator.hierarchy.owner

            UserHierarchy.objects.create(
                user=user,
                parent=owner,
                owner=owner,
            )

        return user


    # ---------------------- Update ----------------------
    def update(self, instance, validated_data):
        request = self.context["request"]
        password = validated_data.pop("password", None)
        validated_data.pop("confirm_password", None)

        # Normal updates
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()
        return instance


# ---------------------- User Role Profile Serializer ----------------------
class OwnerSerializer(  ):
    """Serializer for VSRE Owners."""
    owned_venues = VenueMiniSerializer(many=True, read_only=True)
    owned_service = ServiceMiniSerializer(many=True, read_only=True)
    owned_resoure = ResourceMiniSerializer(many=True, read_only=True)
    
    class Meta(BaseUserSerializer.Meta):
        fields = BaseUserSerializer.Meta.fields + ["owned_venues" "owned_service","owned_resoure"]

class ManagerSerializer(BaseUserSerializer):
    reports_to = serializers.SerializerMethodField()
    managed_venues = VenueMiniSerializer(many=True, read_only=True)
    managed_service = ServiceMiniSerializer(many=True, read_only=True)
    managed_resoure = ResourceMiniSerializer(many=True, read_only=True)

    class Meta(BaseUserSerializer.Meta):
        fields = BaseUserSerializer.Meta.fields + [
            "employee_id",
            "category",
            "skills",
            "qc_required",
            "last_working_day",
            "reports_to",
            "managed_venues",
            "managed_service",
            "managed_resoure",
        ]

    def get_reports_to(self, user):
        hierarchy = getattr(user, "hierarchy", None)
        if not hierarchy:
            return None

        parent = hierarchy.parent
        if not parent:
            return None

        parent_hierarchy = getattr(parent, "hierarchy", None)
        parent_level = parent_hierarchy.level if parent_hierarchy else None

        return {
            "id": parent.id,
            "name": parent.get_full_name(),
            "level": parent_level
        }



class StaffSerializer(BaseUserSerializer):
    """Serializer for VSRE Staff."""
    reports_to = serializers.SerializerMethodField()
    
    assigned_venues = VenueMiniSerializer(many=True, read_only=True)
    assigned_service = ServiceMiniSerializer(many=True, read_only=True)
    assigned_resoure = ResourceMiniSerializer(many=True, read_only=True)

    class Meta(BaseUserSerializer.Meta):
        fields = BaseUserSerializer.Meta.fields + [
            "employee_id",
            "category",
            "skills",
            "target_percent",
            "order_types",
            "last_working_day",
            "reports_to",
            "assigned_venues",
            "assigned_service",
            "assigned_resoure",
        ]
    
    def get_reports_to(self, user):
        hierarchy = getattr(user, "hierarchy", None)
        if not hierarchy:
            return None

        parent = hierarchy.parent
        if not parent:
            return None

        parent_hierarchy = getattr(parent, "hierarchy", None)
        parent_level = parent_hierarchy.level if parent_hierarchy else None

        return {
            "id": parent.id,
            "name": parent.get_full_name(),
            "level": parent_level
        }


class CustomerSerializer(BaseUserSerializer):
    """Serializer for Customers"""
    pass

# ---------------------- UserHierarchy Serializer ----------------------
class UserHierarchySerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    parent_email = serializers.EmailField(source="parent.email", read_only=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta:
        model = UserHierarchy
        fields = '__all__'
        read_only_fields = ('level',)

class ManagerHierarchySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    level = serializers.IntegerField(source="hierarchy.level", read_only=True)
    parent_id = serializers.IntegerField(source="hierarchy.parent_id", read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "name",
            "email",
            "level",
            "parent_id",
        ]

    def get_name(self, obj):
        return obj.get_full_name()
# ---------------------- Registration Serializer ----------------------
class CustomerRegistrationSerializer(BaseUserSerializer):
    """Public registration for customers."""

    def create(self, validated_data):
        validated_data["user_type"] = "CUSTOMER"
        validated_data["created_by"] = None
        return super().create(validated_data)


class VSREOwnerRegistrationSerializer(BaseUserSerializer):
    """Public registration for VSRE owners (requires approval)."""

    def create(self, validated_data):
        request = self.context.get("request")
        validated_data["user_type"] = "VSRE_OWNER"
        validated_data["created_by"] = None
        return super().create(validated_data)


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        username = data.get("username")
        password = data.get("password")
        user = authenticate(request=self.context.get("request"), username=username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        data["user"] = user
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

# ---------------------- PricingModel Serializer ----------------------
class PricingModelSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = PricingModel
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def create(self, validated_data):
        request = self.context.get('request')
        if request and not validated_data.get('created_by'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)


# ---------------------- UserPlan Serializer ----------------------
class UserPlanSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = UserPlan
        fields = '__all__'
        read_only_fields = ('is_active', 'end_date')
