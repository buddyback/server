# urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from devices.views.device_views import DeviceViewSet
from devices.views.session_views import SessionStartView, SessionStopView, SessionStatusView
from devices.views.sessions_statistic_views import SessionStatisticsView

# Router for device viewset
router = DefaultRouter()
router.register(r"devices", DeviceViewSet, basename="device")

# URL patterns
urlpatterns = [
    path("", include(router.urls)),
    path("devices/<uuid:device_id>/start/", SessionStartView.as_view(), name="session-start"),
    path("devices/<uuid:device_id>/stop/", SessionStopView.as_view(), name="session-stop"),
    path("devices/<uuid:device_id>/status/", SessionStatusView.as_view(), name="session-status"),
    path("devices/<uuid:device_id>/statistics/", SessionStatisticsView.as_view(), name="session-statistics"),
]
