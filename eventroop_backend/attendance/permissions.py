from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsVSREOwnerOrReadOnlyForTeam(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        # If owner → full access
        if getattr(user, "is_owner", False):
            return True

        # If manager or staff → read-only
        if getattr(user, "is_manager", False) or getattr(user, "is_vsre_staff", False):
            return request.method in SAFE_METHODS

        # Otherwise → no permissions
        return False
