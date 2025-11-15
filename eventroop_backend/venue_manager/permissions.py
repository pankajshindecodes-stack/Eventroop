#permissions.py
from rest_framework import permissions
from rest_framework import permissions
from .models import CustomUser 
class IsOwnerOrManagerPermission(permissions.BasePermission):
    """
    Custom permission:
    - Owner: full access to own objects
    - Manager: access only to assigned objects
    - Staff: limited access
    """

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.user_type == CustomUser.UserTypes.VSRE_OWNER:
            return obj.owner == user

        elif user.user_type in [
            CustomUser.UserTypes.VSRE_MANAGER,
            CustomUser.UserTypes.LINE_MANAGER,
        ]:
            # Check if manager is assigned to this object
            return hasattr(obj, "manager") and obj.manager == user

        elif user.user_type == CustomUser.UserTypes.VSRE_STAFF:
            # Staff can view only assigned
            return hasattr(obj, "assigned_to") and user in obj.assigned_to.all()

        return False

class DashboardAccessPermission(permissions.BasePermission):
    """
    Role-based permission for Venue, Service, Event, etc.
    Includes view (GET) access control based on user role.
    """

    def has_permission(self, request, view):
        user = request.user
        user_type = getattr(user, "user_type", None)

        # Everyone must be authenticated for any request
        if not user.is_authenticated:
            return False

        # READ (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Allow all authenticated roles (list & detail checks in has_object_permission)
            return True

        # CREATE (POST)
        if request.method == 'POST':
            return user_type == "VSRE_OWNER"

        # UPDATE / DELETE — check in has_object_permission
        return True


    def has_object_permission(self, request, view, obj):
        """
        Object-level permissions (for retrieve, update, delete)
        """

        user = request.user
        user_type = getattr(user, "user_type", None)

        # READ (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            # Master admin can view everything
            if user_type == "MASTER_ADMIN":
                return True

            # Owner can only view their own venues
            if user_type == "VSRE_OWNER" and getattr(obj, "owner", None) == user.owner_profile:
                return True

            # Manager can only view venues assigned to them
            if user_type == "VSRE_MANAGER" and getattr(obj, "manager", None) == user.manager_profile:
                return True

            return False  # other roles cannot view

        # CREATE handled in has_permission

        # UPDATE (PUT/PATCH)
        if request.method in ['PUT', 'PATCH']:
            if user_type == "VSRE_MANAGER" and getattr(obj, "manager", None) == user.manager_profile:
                return True
            if user_type == "VSRE_OWNER" and getattr(obj, "owner", None) == user.owner_profile:
                return True
            return False

        # DELETE
        if request.method == 'DELETE':
            # Master Admin can permanently delete
            if user_type == "MASTER_ADMIN":
                return True

            # VSRE_OWNER can soft delete only their own
            if user_type == "VSRE_OWNER" and getattr(obj, "owner", None) == user.owner_profile:
                return True

        return False
