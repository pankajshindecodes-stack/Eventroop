import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notification.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eventroop_backend.settings')
http_application = get_asgi_application()
application = ProtocolTypeRouter({
    'http': http_application,
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})

app = application