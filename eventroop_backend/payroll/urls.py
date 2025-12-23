
# urls.py
from django.urls import path
from .views import (
    SalaryStructureListCreateView,
    SalaryStructureDetailView,
    SalaryIncrementView,
    CurrentSalaryView,
    SalaryHistoryView
)
app_name = 'payroll'

urlpatterns = [
    # Salary structure CRUD
    path('salary-structures/', SalaryStructureListCreateView.as_view(), name='salary-structure-list-create'),
    path('salary-structures/<int:pk>/', SalaryStructureDetailView.as_view(), name='salary-structure-detail'),
    
    # Salary increment
    path('salary-structures/increment/', SalaryIncrementView.as_view(), name='salary-increment'),
    
    # Current salary and history
    path('salary-structures/current/', CurrentSalaryView.as_view(), name='current-salary'),
    path('salary-structures/history/', SalaryHistoryView.as_view(), name='salary-history'),
]