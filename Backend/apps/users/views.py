from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAdminUserRole
from .serializers import (
    AdminUserUpdateSerializer,
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

User = get_user_model()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        registration_data = request.data.copy()
        registration_data.pop("role", None)
        serializer = UserRegistrationSerializer(data=registration_data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "Registration successful.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminUserListCreateAPIView(generics.ListCreateAPIView):
    """
    Role-Gated: Admin only.
    GET /api/admin/users/
    POST /api/admin/users/
    """
    permission_classes = [IsAdminUserRole]
    queryset = User.objects.all().order_by("-date_joined")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserRegistrationSerializer
        return UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


class AdminUserDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    Role-Gated: Admin only.
    GET /api/admin/users/:id/
    PATCH /api/admin/users/:id/
    DELETE /api/admin/users/:id/
    """
    permission_classes = [IsAdminUserRole]
    queryset = User.objects.all()
    serializer_class = AdminUserUpdateSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.id == request.user.id:
            return Response(
                {"detail": "Cannot delete your own account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        self.perform_destroy(instance)
        return Response(
            {"message": "User deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )
        
class AnalystListAPIView(generics.ListAPIView):
    permission_classes = [IsAdminUserRole]
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = User.objects.filter(
            role=User.Role.ANALYST
        ).order_by("-date_joined")

        search = self.request.query_params.get(
            "search"
        )

        status_param = self.request.query_params.get(
            "status"
        )

        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
            )

        if status_param == "active":
            queryset = queryset.filter(
                is_active=True
            )

        elif status_param == "inactive":
            queryset = queryset.filter(
                is_active=False
            )

        return queryset