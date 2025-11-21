from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied

from .permissions import VenueAccessPermission
from .serializers import VenueSerializer, PhotosSerializer
from accounts.models import CustomUser
from .models import Venue, Photos

class VenueViewSet(viewsets.ModelViewSet):
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated, VenueAccessPermission]

    # --------------------------------------------------------
    # FILTER VENUES BASED ON ROLE
    # --------------------------------------------------------
    def get_queryset(self):
        user = self.request.user

        if user.is_owner:
            print(Venue.objects.filter(owner=user, is_deleted=False))
            return Venue.objects.filter(owner=user, is_deleted=False)

        if user.is_manager:
            return Venue.objects.filter(manager=user, is_deleted=False)

        if user.is_staff_role:
            return Venue.objects.filter(staff=user, is_deleted=False)

        return Venue.objects.none()

    # --------------------------------------------------------
    # CREATE WITH OWNER
    # --------------------------------------------------------

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_owner:
            raise PermissionDenied("Only owners can create venues.")
        serializer.save(owner=user,is_active=True)

    # --------------------------------------------------------
    # SOFT DELETE
    # --------------------------------------------------------
    def perform_destroy(self, instance):
        instance.soft_delete()

    # --------------------------------------------------------
    # ASSIGN MANAGER
    # --------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="assign-manager")
    def assign_manager(self, request, pk=None):
        venue = self.get_object()
        user = request.user

        manager_id = request.data.get("manager_id")
        if not manager_id:
            return Response({"error": "manager_id is required"}, status=400)

        try:
            manager = CustomUser.objects.get(
                id=manager_id,
                user_type__in=["VSRE_MANAGER", "LINE_MANAGER"]
            )
        except CustomUser.DoesNotExist:
            return Response({"error": "Manager not found"}, status=404)

        # Owner can assign any manager under him
        if user.is_owner:
            if manager.owner != user:
                return Response({"error": "Manager does not belong to you"}, status=status.HTTP_403_FORBIDDEN)

        # Manager can only assign staff to HIS venue
        elif user.is_manager:
            if venue.manager_id != user.id:
                return Response({"error": "You are not manager of this venue"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        venue.manager = manager
        venue.save()
        return Response({"message": "Manager assigned successfully"})

    # --------------------------------------------------------
    # ASSIGN STAFF
    # --------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="assign-staff")
    def assign_staff(self, request, pk=None):
        venue = self.get_object()
        user = request.user
        staff_ids = request.data.get("staff_ids", [])

        if not isinstance(staff_ids, list):
            return Response({"error": "staff_ids must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        staff_members = CustomUser.objects.filter(
            id__in=staff_ids,
            user_type="VSRE_STAFF"
        )

        # Owner: staff must belong to owner
        if user.is_owner:
            for s in staff_members:
                if s.owner != user:
                    return Response(
                        {"error": f"Staff {s.id} does not belong to you"},
                        status=status.HTTP_403_FORBIDDEN
                    )

        # Manager: can only assign staff to HIS venue
        elif user.is_manager:
            if venue.manager_id != user.id:
                return Response({"error": "You are not manager of this venue"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"error": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        venue.staff.set(staff_members)
        venue.save()

        return Response({"message": "Staff assigned successfully"})

    # --------------------------------------------------------
    # UPLOAD PHOTO
    # --------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="upload-photo")
    def upload_photo(self, request, pk=None):
        venue = self.get_object()
        image = request.FILES.get("image")
        is_primary = request.data.get("is_primary", False)

        if not image:
            return Response({"error": "Image is required"}, status=400)

        ct = ContentType.objects.get_for_model(Venue)

        # If marking this as primary -> unset previous primary
        if str(is_primary).lower() in ["true", "1", "yes"]:
            is_primary = True
            Photos.objects.filter(
                content_type=ct,
                object_id=venue.id,
                is_primary=True
            ).update(is_primary=False)
        else:
            is_primary = False

        photo = Photos.objects.create(
            image=image,
            is_primary=is_primary,
            content_type=ct,
            object_id=venue.id
        )

        return Response(PhotosSerializer(photo).data, status=status.HTTP_201_CREATED)
