from rest_framework.routers import DefaultRouter
from .views import *

app_name = 'booking'
router = DefaultRouter()
router.register(r'public-venues', PublicVenueViewSet, basename='public-venues')
router.register(r'public-services', PublicServiceViewSet, basename='public-services')
router.register(r'patients', PatientViewSet, basename='patients')
router.register(r'location', LocationViewSet, basename='location')
router.register(r'packages', PackageViewSet, basename='package')
router.register(r'bookings', BookingViewSet, basename='booking')
router.register(r'booking-services', BookingServiceViewSet, basename='booking-service')
# router.register(r'invoices', InvoiceViewSet, basename='invoice')
urlpatterns = router.urls
