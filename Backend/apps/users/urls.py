from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AdminUserDetailAPIView,
    AdminUserListCreateAPIView,
    CustomTokenObtainPairView,
    MeAPIView,
    RegisterAPIView,
)

urlpatterns = [
    path(
        "register/",
        RegisterAPIView.as_view(),
        name="register",
    ),
    path(
        "login/",
        CustomTokenObtainPairView.as_view(),
        name="login",
    ),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "me/",
        MeAPIView.as_view(),
        name="me",
    ),
    # Admin User endpoints
    path(
        "admin-users/",
        AdminUserListCreateAPIView.as_view(),
        name="admin-users-list",
    ),
    path(
        "admin-users/<int:pk>/",
        AdminUserDetailAPIView.as_view(),
        name="admin-users-detail",
    ),
]