from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.services import auth_service, mfa_service

from .permissions import IsAuthenticatedWithMfa
from .serializers import LoginSerializer, MfaVerifySerializer, RegisterSerializer, UserSerializer


class CsrfView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request):
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = auth_service.register_user(
            username=serializer.validated_data["username"],
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = auth_service.login_user(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )

        if result is None:
            return Response({"detail": "Credenciais inválidas."}, status=status.HTTP_401_UNAUTHORIZED)

        if result.mfa_challenge is not None:
            # Senha correta, falta o segundo fator: nenhuma sessão autenticada
            # foi criada ainda. O cliente segue para /auth/mfa/verify/.
            return Response(result.mfa_challenge)

        return Response(UserSerializer(result.user).data)


class MfaVerifyView(APIView):
    """Segunda etapa do login: código TOTP (6 dígitos) ou código de backup."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "mfa"

    def post(self, request):
        serializer = MfaVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            verification = mfa_service.verify_challenge(request, serializer.validated_data["token"])
        except mfa_service.MfaInvalidToken as exc:
            return Response(
                {"detail": "Código inválido.", "attempts_left": exc.attempts_left},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except mfa_service.MfaChallengeError:
            return Response(
                {"detail": "Verificação expirada. Entre novamente com usuário e senha.", "restart": True},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = UserSerializer(verification.user).data
        if verification.backup_codes:
            data["backup_codes"] = verification.backup_codes
        return Response(data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        auth_service.logout_user(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticatedWithMfa]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
