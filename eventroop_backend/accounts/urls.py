from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework import routers
from .views import *
app_name = 'venue_manager'

router = routers.DefaultRouter()

router.register(r'master-admin', MasterViewSet, basename='master-admin')
router.register(r'vsre-manager', ManagerViewSet, basename='vsre-manager')
router.register(r'vsre-staff', StaffViewSet, basename='vsre-staff')
router.register(r'user-hierarchy', UserHierarchyViewSet, basename='user-hierarchy')
router.register(r'pricing-models', PricingModelViewSet, basename='pricing-models')
router.register(r'user-plans', UserPlanViewSet, basename='user-plans')

urlpatterns = router.urls


urlpatterns += [
    path('register/customer/', CustomerRegistrationView.as_view()),
    path('register/owner/', VSREOwnerRegistrationView.as_view()),
    path('login/', LoginView.as_view()),
    path('logout/', LogoutView.as_view()),
    path('change-password/', ChangePasswordView.as_view()),
    path('token/refresh/', TokenRefreshView.as_view()),
    path('profile/', UserProfileView.as_view()),
]
