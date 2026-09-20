import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

logger = logging.getLogger("apps.accounts")


def register_user(*, username: str, email: str, password: str) -> User:
    user = User.objects.create_user(username=username, email=email, password=password)
    logger.info("user_registered", extra={"user_id": user.id})
    return user


def login_user(request, *, username: str, password: str) -> User | None:
    user = authenticate(request, username=username, password=password)

    if user is None:
        logger.warning("login_failed", extra={"origin": request.META.get("REMOTE_ADDR")})
        return None

    login(request, user)
    logger.info("login_succeeded", extra={"user_id": user.id})
    return user


def logout_user(request) -> None:
    user_id = request.user.id
    logout(request)
    logger.info("logout", extra={"user_id": user_id})
