from django.urls import path
from .views import AllVenuesView, VenueDetailView

app_name = 'booking'

urlpatterns = [
    path("all-venues/", AllVenuesView.as_view(), name="all-venues"),
    path("venue-detail/<pk>/", VenueDetailView.as_view(), name="venue-detail"),
]
