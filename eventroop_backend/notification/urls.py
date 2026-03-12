from django.urls import path
from . import views

app_name = 'payroll'

urlpatterns = [
    # List & count
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', views.unread_count, name='notification-unread-count'),

    # Bulk actions
    path('mark-all-read/', views.mark_all_read, name='notification-mark-all-read'),
    path('clear/', views.clear_all, name='notification-clear-all'),

    # Single item actions
    path('<int:pk>/read/', views.mark_read, name='notification-mark-read'),
    path('<int:pk>/', views.delete_notification, name='notification-delete'),
]