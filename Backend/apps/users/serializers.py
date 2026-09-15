from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "email": self.user.email,
            "role": self.user.role,
            "first_name": self.user.first_name,
            "last_name": self.user.last_name,
            "is_active": self.user.is_active,
        }
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
    )
    password_confirm = serializers.CharField(
        write_only=True,
    )
    role = serializers.ChoiceField(
        choices=User.Role.choices,
        default=User.Role.VIEWER,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "role",
        ]

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        role = validated_data.pop("role", User.Role.VIEWER)

        user = User(
            **validated_data,
            role=role,
        )
        user.set_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [
            "id",
            "date_joined",
            "last_login",
        ]


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=6,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "password",
        ]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        if password:
            instance.set_password(password)
        return super().update(instance, validated_data)