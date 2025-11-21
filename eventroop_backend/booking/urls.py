from rest_framework.routers import DefaultRouter
from .views import PublicVenueViewSet

app_name = 'booking'
router = DefaultRouter()
router.register("public-venues", PublicVenueViewSet, basename="public-venues")

urlpatterns = router.urls
