from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import views

app_name = 'payroll'



router = DefaultRouter()
router.register(r'salary-structures', views.SalaryStructureViewSet, basename='salary-structure')

urlpatterns = [
    # Salary Structure endpoints
    path('', include(router.urls)),
        
    # Salary Transaction endpoints
    path('transactions/', views.SalaryTransactionView.as_view(), name='salary-transaction-list-create'),
    path('transactions/<uuid:transaction_id>/mark-paid/', views.MarkSalaryAsPaidView.as_view(), name='salary-transaction-mark-paid'),
]