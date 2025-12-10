from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsSuperUserOrReadOnly(BasePermission):
    """
    Superusers have full access.
    All other users: read-only
    """

    def has_permission(self, request, view):
        # Allow safe (GET, HEAD, OPTIONS) for everyone
        if request.method in SAFE_METHODS:
            return True

        # Write permissions only for superusers
        return request.user and request.user.is_superuser
