from rest_framework.routers import DefaultRouter

from .views import PostureDataViewSet

router = DefaultRouter()
router.register(r'posture-data', PostureDataViewSet, basename='posturedata')

urlpatterns = router.urls
