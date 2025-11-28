from rest_framework import viewsets, views,status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from .permissions import VenueAccessPermission,CanAssignUsers
from .serializers import VenueSerializer, PhotosSerializer
from accounts.models import CustomUser
from accounts.serializers import VenueMiniSerializer,ServiceMiniSerializer,ResourceMiniSerializer
from .models import *
from .validations import *

class VenueViewSet(viewsets.ModelViewSet):
    serializer_class = VenueSerializer
    permission_classes = [IsAuthenticated, VenueAccessPermission]
    filterset_fields = {
        "city": ["iexact", "icontains"],
        "is_active": ["exact"],
        "is_deleted": ["exact"],
        "manager": ["exact"],
        "staff": ["exact"],
        "capacity": ["gte", "lte", "exact"],
        "price_per_event": ["gte", "lte"],
        "rooms": ["gte", "lte"],
        "floors": ["gte", "lte"],
        "external_decorators_allow": ["exact"],
        "external_caterers_allow": ["exact"],
    }
    search_fields = [
        "name",
        "description",
        "address",
        "city",
    ]

    # --------------------------------------------------------
    # FILTER VENUES BASED ON ROLE
    # --------------------------------------------------------
    def get_queryset(self):
        user = self.request.user

        if user.is_owner:
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

class EntityAssignUsersAPI(views.APIView):
    permission_classes = [IsAuthenticated, CanAssignUsers]

    # ENTITY → (Model, MiniSerializer)
    ENTITY_MODELS = {
        "venue": (Venue, VenueMiniSerializer),
        "service": (Service, ServiceMiniSerializer),
        "resource": (Resource, ResourceMiniSerializer),
    }

    # -------------------------------------------------------
    # POST → Assign managers + staff to entity
    # -------------------------------------------------------
    def post(self, request, entity_type):
        user = request.user
        entity_id = request.data.get("entity_id", None)
        # Detect entity + serializer
        meta = self.ENTITY_MODELS.get(entity_type)
        if not meta:
            return Response({"error": "Invalid entity type"}, status=400)

        model, _ = meta

        entity = get_object_or_404(model, id=entity_id)

        # Extract data
        manager_ids = request.data.get("manager_ids", [])
        staff_ids = request.data.get("staff_ids", [])

        # Pre-fetch
        managers = CustomUser.objects.filter(
            id__in=manager_ids,
            user_type__in=["VSRE_MANAGER", "LINE_MANAGER"]
        )
        staff_members = CustomUser.objects.filter(
            id__in=staff_ids,
            user_type="VSRE_STAFF"
        )

        # Permission checks
        try:
            validate_users_exist(manager_ids, staff_ids)
            if user.is_owner:
                validate_owner_permissions(user, managers, staff_members)

            elif user.is_manager:
                validate_manager_permissions(user, entity, manager_ids, staff_members)

            else:
                raise PermissionError("Not allowed")

        except PermissionError as e:
            return Response({"error": str(e)}, status=403)

        # Assign managers
        if manager_ids:
            entity.manager.set(managers)

            # Auto-assign staff under these managers
            auto_staff = auto_assign_staff(manager_ids)
            staff_members = (staff_members | auto_staff).distinct()

        # Assign staff
        entity.staff.set(staff_members)
        entity.save()

        return Response({
            "message": f"Users assigned successfully to {entity_type}",
            "entity_id": entity.id,
            "assigned_managers": managers.values("id", "first_name", "last_name"),
            "assigned_staff": staff_members.values("id", "first_name", "last_name"),
        })

    # -------------------------------------------------------
    # GET → Show assigned + assignable entities for a user
    # -------------------------------------------------------
    def get(self, request, entity_type):
        request_user = request.user

        # Detect entity + serializer
        meta = self.ENTITY_MODELS.get(entity_type)
        if not meta:
            return Response({"error": "Invalid entity type"}, status=400)

        model, MiniSerializer = meta

        qs = model.objects.filter(is_active=True)

        if request_user.is_owner:
            qs = qs.filter(owner=request_user)

        elif request_user.is_manager:
            qs = qs.filter(managers=request_user)

        else:
            return Response({"error": "Not allowed"}, status=403)

        assignable_data = MiniSerializer(qs, many=True).data

        return Response({
            "entity_type": entity_type,
            "assignable_entities": assignable_data,
        })
