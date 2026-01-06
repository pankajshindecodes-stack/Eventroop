from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

app_name = 'payroll'

router = DefaultRouter()
router.register(r'salary-structures', views.SalaryStructureViewSet, basename='salary-structure')

urlpatterns = [
    # Salary Structure endpoints
    path('', include(router.urls)),
    path("salary-transactions/", views.SalaryReportAPIView.as_view(),name="salary-transactions-list"),
    path("salary-transactions/<int:pk>/", views.SalaryReportAPIView.as_view(),name="salary-transactions-detail"),
]