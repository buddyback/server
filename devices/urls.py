from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeviceViewSet

# Main router for top-level endpoints
router = DefaultRouter()
router.register(r"devices", DeviceViewSet, basename="device")

urlpatterns = [
    path("", include(router.urls)),
]
