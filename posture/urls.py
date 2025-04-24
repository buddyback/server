from django.urls import path
from rest_framework.routers import DefaultRouter

from posture.views.device_posture_data_views import PostureDataViewSet
from posture.views.user_posture_data_views import UserPostureDataByDeviceViewSet

router = DefaultRouter()
router.register(r'posture-data', PostureDataViewSet, basename='posturedata')

urlpatterns = router.urls + [
    path(
        'devices/<uuid:device_id>/posture-data/',
        UserPostureDataByDeviceViewSet.as_view({'get': 'list'}),
        name='user-device-posture-data'
    ),
]
