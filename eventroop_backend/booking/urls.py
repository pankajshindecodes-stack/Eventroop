from django.urls import path
from .views import AllVenuesView, VenueDetailView

urlpatterns = [
    path("venues/", AllVenuesView.as_view(), name="all-venues"),
    path("venues/<int:id>/", VenueDetailView.as_view(), name="venue-detail"),
]
