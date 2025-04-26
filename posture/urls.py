from django.urls import path
from rest_framework.routers import DefaultRouter

from posture.views.device_posture_data_views import PostureDataViewSet
from posture.views.user_posture_data_views import UserPostureDataByDeviceViewSet

router = DefaultRouter()
router.register(r"posture-data", PostureDataViewSet, basename="posturedata")

urlpatterns = router.urls + [
    # Base list view for user's device posture data
    path(
        "devices/<uuid:device_id>/posture-data/",
        UserPostureDataByDeviceViewSet.as_view({"get": "list"}),
        name="user-device-posture-data",
    ),
    # Daily chart view
    path(
        "devices/<uuid:device_id>/posture-data/daily-chart/",
        UserPostureDataByDeviceViewSet.as_view({"get": "daily_chart"}),
        name="user-device-posture-daily-chart",
    ),
    # Weekly chart view
    path(
        "devices/<uuid:device_id>/posture-data/weekly-chart/",
        UserPostureDataByDeviceViewSet.as_view({"get": "weekly_chart"}),
        name="user-device-posture-weekly-chart",
    ),
    # Monthly chart view
    path(
        "devices/<uuid:device_id>/posture-data/monthly-chart/",
        UserPostureDataByDeviceViewSet.as_view({"get": "monthly_chart"}),
        name="user-device-posture-monthly-chart",
    ),
]
