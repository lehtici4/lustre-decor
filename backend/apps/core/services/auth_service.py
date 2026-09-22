import logging
from dataclasses import dataclass

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

from apps.core.services import mfa_service

logger = logging.getLogger("apps.accounts")


def register_user(*, username: str, email: str, password: str) -> User:
    user = User.objects.create_user(username=username, email=email, password=password)
    logger.info("user_registered", extra={"user_id": user.id})
    return user


@dataclass
class LoginResult:
    user: User | None = None
    """Preenchido quando a sessão já foi criada (conta isenta de MFA)."""
    mfa_challenge: dict | None = None
    """Preenchido quando falta o segundo fator — sessão ainda NÃO autenticada."""


def login_user(request, *, username: str, password: str) -> LoginResult | None:
    user = authenticate(request, username=username, password=password)

    if user is None:
        logger.warning("login_failed", extra={"origin": request.META.get("REMOTE_ADDR")})
        return None

    if not mfa_service.is_exempt(user):
        # Senha correta, mas a sessão só nasce depois do TOTP
        # (ver apps/core/services/mfa_service.py).
        logger.info("login_password_ok", extra={"user_id": user.id})
        return LoginResult(mfa_challenge=mfa_service.start_challenge(request, user))

    login(request, user)
    logger.info("login_succeeded", extra={"user_id": user.id, "mfa": False, "mfa_exempt": True})
    return LoginResult(user=user)


def logout_user(request) -> None:
    user_id = request.user.id
    logout(request)
    logger.info("logout", extra={"user_id": user_id})
