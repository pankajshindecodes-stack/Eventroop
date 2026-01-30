from rest_framework.routers import DefaultRouter
from .views import *

app_name = 'booking'
router = DefaultRouter()

# Public endpoints (no authentication required)
router.register(r'public-venues', PublicVenueViewSet, basename='public-venues')
router.register(r'public-services', PublicServiceViewSet, basename='public-services')

# Authenticated endpoints
router.register(r'patients', PatientViewSet, basename='patients')
router.register(r'location', LocationViewSet, basename='location')
router.register(r'packages', PackageViewSet, basename='package')

router.register(r"bookings", InvoiceBookingViewSet, basename="bookings")
router.register(r"invoices", TotalInvoiceViewSet, basename="invoices")
router.register(r"payments", PaymentViewSet, basename="payments")

urlpatterns = router.urls
