from venue_manager.models import Venue,Service
from .serializers import VenueSerializer,ServiceSerializer
from rest_framework import viewsets, permissions
from rest_framework.pagination import PageNumberPagination

class PublicVenueViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Single API for:
      - GET /venues/          → list venues with filters
      - GET /venues/<id>/     → venue details
    """
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = PageNumberPagination
    lookup_field = "pk"

    queryset = Venue.objects.filter(is_deleted=False, is_active=True).order_by("id")

    filterset_fields = {
        "city": ["iexact", "icontains"],
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
        "address",
        "city",
        "contact",
    ]

class PublicServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Single API for:
      - GET /services/          → list services with filters
      - GET /services/<id>/     → service details
    """
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = PageNumberPagination
    lookup_field = "pk"

    queryset = Service.objects.filter(is_deleted=False, is_active=True).order_by("id")

    filterset_fields = {
        # "category": ["iexact", "icontains"],
        # "sub_category": ["iexact", "icontains"],
        "city": ["iexact", "icontains"],
        # "starting_price": ["gte", "lte"],
        # "rating": ["gte", "lte", "exact"],
    }

    search_fields = [
        "name",
        "description",
        "category",
        "sub_category",
        "city",
    ]
