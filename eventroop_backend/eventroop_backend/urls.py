from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "Value Occations Admin Panel"
admin.site.site_title = "Value Occations Admin"
admin.site.index_title = "Welcome to Value Occations Administration"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include(('accounts.urls', 'accounts'), namespace='accounts')),
    path('management/', include(('venue_manager.urls', 'venue_manager'), namespace='venue_manager')),
    path('booking/', include(('booking.urls', 'booking'), namespace='booking')),
    path('attendance/', include(('attendance.urls', 'attendance'), namespace='attendance')),
]

# Serve media and static files during development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
