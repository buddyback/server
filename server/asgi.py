import os

# Configure Django settings at the beginning
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "server.settings")

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# Initialize Django ASGI application first
django_asgi_app = get_asgi_application()

# Import your websocket_urlpatterns - only after Django is initialized
import devices.routing

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(devices.routing.websocket_urlpatterns)),
    }
)
