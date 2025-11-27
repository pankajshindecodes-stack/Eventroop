from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

app_name = 'venue_manager'

router = DefaultRouter()
router.register(r'venues', VenueViewSet, basename='venue')

urlpatterns = [
    path('', include(router.urls)),
    path("assign-users/<entity_type>/<entity_id>/",EntityAssignUsersAPI.as_view(),name="assign-users"),

]

