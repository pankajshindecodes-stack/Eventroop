from rest_framework.permissions import BasePermission, SAFE_METHODS

class VenueAccessPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.user.can_manage_entity(obj)
