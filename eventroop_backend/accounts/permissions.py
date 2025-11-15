from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsMasterAdmin(BasePermission):
    """Allow only MASTER_ADMIN users to access."""
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.user_type == "MASTER_ADMIN"
        )

class IsVSREOwner(BasePermission):
    """Allow only VSRE_OWNER."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            request.user.user_type == "VSRE_OWNER"
        )


class IsVSREOwnerOrManager(BasePermission):
    """Allow both VSRE_OWNER and VSRE_MANAGER."""
    ALLOWED_ROLES = ["VSRE_OWNER", "VSRE_MANAGER"]

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.user_type in self.ALLOWED_ROLES
        )

class IsCreator(BasePermission):
    """Allow access only to objects created by the user."""

    def has_object_permission(self, request, view, obj):
        return obj.created_by == request.user
