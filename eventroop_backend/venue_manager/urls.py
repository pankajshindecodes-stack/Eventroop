from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VenueViewSet

app_name = 'venue_manager'

router = DefaultRouter()
router.register(r'venues', VenueViewSet, basename='venue')

urlpatterns = [
    path('', include(router.urls)),
]

