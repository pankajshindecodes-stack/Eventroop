from venue_manager.models import Venue,Service
from venue_manager.serializers import VenueSerializer,ServiceSerializer
from rest_framework import viewsets, permissions,status
from .serializers import *
from .models import Patient,Package
from .filters import EntityFilter
from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.response import Response


class PublicVenueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Single API for:
      - GET /venues/          → list venues with filters
      - GET /venues/<id>/     → venue details
    """
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]
    
    lookup_field = "pk"
    queryset = Venue.objects.filter(is_deleted=False, is_active=True).order_by("id")

    filterset_fields = {
        "location__city": ["iexact", "icontains"],
        "location__state": ["iexact", "icontains"],
        "capacity": ["gte", "lte", "exact"],
        "price_per_event": ["gte", "lte"],
        "rooms": ["gte", "lte"],
        "floors": ["gte", "lte"],
        "external_decorators_allow": ["iexact"],
        "external_caterers_allow": ["iexact"],
    }

    search_fields = [
        "name",
        "description",
        "location__building_name",
        "location__address_line1",
        "location__address_line2",
        "location__locality",
        "location__city",
        "location__state",
    ]

class PublicServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Single API for:
      - GET /services/          → list services with filters
      - GET /services/<id>/     → service details
    """
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]
    
    filterset_class = EntityFilter
    lookup_field = "pk"

    queryset = Service.objects.filter(is_deleted=False, is_active=True).order_by("id")

    filterset_fields = {
        # "category": ["iexact", "icontains"],
        # "sub_category": ["iexact", "icontains"],
        "city": ["iexact", "icontains"],
        # "tags": ["iexact", "icontains"],
        # "starting_price": ["gte", "lte"],
        # "rating": ["gte", "lte", "exact"],

    }

    search_fields = [
        "venue__name",
        "name",
        "description",
        "address",
        "city",
        "contact",
        "website",
        "tags",
        "quick_info"
    ]

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Owner → return all patient data
        if user.is_owner:
            return Patient.objects.filter(
                Q(registered_by__hierarchy__owner=user) |
                Q(registered_by=user)
            )


        # Manager/Staff → only their own patients
        return Patient.objects.filter(registered_by=user)

    def perform_create(self, serializer):
        """
        Set registered_by = request.user automatically
        """
        serializer.save(registered_by=self.request.user)

class LocationViewSet(viewsets.ModelViewSet):
    serializer_class = LocationSerializer

    filterset_fields = ["location_type","user__first_name","user__email","user__mobile_number", "city", "state"]
    search_fields = [
        "user__first_name",
        "user__email",
        "user__mobile_number"
        "building_name",
        "address_line1",
        "locality",
        "city",
        "state",
        "postal_code",
    ]
    
    def get_queryset(self):
        user = self.request.user

        # Admin → see all locations
        if user.is_superuser:
            qs = Location.objects.all()
        else:
            qs = Location.objects.filter(user=user)

        return qs.order_by("-id")  # or any default ordering you prefer
    
    def perform_create(self, serializer):
        # Automatically set the user to the requesting user
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # Ensure user cannot be changed on update
        serializer.save(user=self.request.user)

class PackageViewSet(viewsets.ModelViewSet):
    queryset = Package.objects.all()
    serializer_class = PackageSerializer
    filterset_fields = ['package_type', 'is_active', 'owner', 'content_type__model']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'price', 'name']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return PackageListSerializer
        return PackageSerializer

    def get_queryset(self):
        user = self.request.user
        # Owners can only see their own packages, staff can see all
        if user.is_vsre_staff:
            return Package.objects.filter(owner=user.hierarchy.owner)
        return Package.objects.filter(owner=user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if not self.request.user.is_owner:
            return Response(
                {'detail': 'You do not have permission to update this package.'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_owner:
            return Response(
                {'detail': 'You do not have permission to delete this package.'},
                status=status.HTTP_403_FORBIDDEN
            )
        instance.delete()

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """Filter packages by type"""
        pkg_type = request.query_params.get('type')
        if not pkg_type:
            return Response(
                {'error': 'type parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        packages = self.get_queryset().filter(package_type=pkg_type)
        serializer = self.get_serializer(packages, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_belongs_to(self, request):
        """
        Example:
        /booking/packages/by_belongs_to/?content_type=venue&object_id=3
        """
        content_type_name = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')

        if not content_type_name or not object_id:
            return Response(
                {'error': 'content_type and object_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Resolve model name → ContentType row
            content_type = ContentType.objects.get(model=content_type_name.lower())
        except ContentType.DoesNotExist:
            return Response(
                {'error': f'Invalid content_type: {content_type_name}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        packages = self.get_queryset().filter(
            content_type=content_type,
            object_id=object_id
        )

        serializer = self.get_serializer(packages, many=True)
        return Response(serializer.data)