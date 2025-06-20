from django.urls import path

from authentication.views import CustomTokenObtainPairView, CustomTokenRefreshView, CustomTokenVerifyView, LogoutView

urlpatterns = [
    # HTTPONLY COOKIES LOGIN SYSTEM
    path("jwt/create/", CustomTokenObtainPairView.as_view()),
    path("jwt/refresh/", CustomTokenRefreshView.as_view()),
    path("jwt/verify/", CustomTokenVerifyView.as_view()),
    path("logout/", LogoutView.as_view()),
]
