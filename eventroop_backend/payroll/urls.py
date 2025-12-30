from django.urls import path
from . import views

app_name = 'salary'

urlpatterns = [
    # Salary Structure endpoints
    path('structures/', views.SalaryStructureListCreateView.as_view(), name='salary-structure-list-create'),
    path('structures/<int:pk>/', views.SalaryStructureDetailView.as_view(), name='salary-structure-detail'),
    
    # Salary Increment endpoint
    path('increment/', views.SalaryIncrementView.as_view(), name='salary-increment'),
    
    # Salary Transaction endpoints
    path('transactions/', views.SalaryTransactionView.as_view(), name='salary-transaction-list-create'),
    path('transactions/<uuid:transaction_id>/mark-paid/', views.MarkSalaryAsPaidView.as_view(), name='salary-transaction-mark-paid'),
]