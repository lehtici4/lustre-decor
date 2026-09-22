from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Este nome de usuário já está em uso.")
        return value

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Este e-mail já está cadastrado.")
        return value

    def validate_password(self, value: str) -> str:
        password_validation.validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class MfaVerifySerializer(serializers.Serializer):
    # 6 dígitos (TOTP) ou código de backup (8 caracteres do StaticToken).
    token = serializers.RegexField(r"^\s*[A-Za-z0-9 ]{6,16}\s*$", max_length=32)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff", "mfa_enabled"]
        read_only_fields = fields

    mfa_enabled = serializers.SerializerMethodField()

    def get_mfa_enabled(self, user) -> bool:
        from apps.core.services import mfa_service

        return mfa_service.has_confirmed_totp(user)
