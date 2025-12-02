from rest_framework.routers import DefaultRouter
from .views import PublicVenueViewSet,PublicServiceViewSet

app_name = 'booking'
router = DefaultRouter()
router.register("public-venues", PublicVenueViewSet, basename="public-venues")
router.register("public-services", PublicServiceViewSet, basename="public-services")

urlpatterns = router.urls
