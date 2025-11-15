from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from venue_manager.models import Venue
from .serializers import VenueSerializer
from .helpers import get_city_filtered_queryset  # assuming helper is in utils.py


class AllVenuesView(ListAPIView):
    """
    List all venues, optionally filtered by city (?city=Pune)
    """
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = PageNumberPagination
    def get_queryset(self):
        queryset = Venue.objects.filter(is_deleted=False, is_active=True)
        return get_city_filtered_queryset(self.request, queryset)


class VenueDetailView(RetrieveAPIView):
    """
    Retrieve a single venue by ID, with optional city filtering (?city=Pune)
    """
    serializer_class = VenueSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "pk"

    def get_queryset(self):
        queryset = Venue.objects.filter(is_deleted=False, is_active=True)
        return get_city_filtered_queryset(self.request, queryset)
